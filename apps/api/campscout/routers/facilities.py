from __future__ import annotations

import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from campscout.db import get_db
from campscout.models.availability import CurrentAvailability

router = APIRouter(prefix="/api")


@router.get("/facilities/{facility_id}/availability")
async def get_facility_availability(
    facility_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    month: str | None = Query(default=None, description="YYYY-MM-DD first of month"),
) -> dict:
    """Return per-site availability grid for a facility."""
    stmt = select(
        CurrentAvailability.month,
        CurrentAvailability.grid,
        CurrentAvailability.scraped_at,
    ).where(CurrentAvailability.facility_id == facility_id)

    if month:
        stmt = stmt.where(CurrentAvailability.month == month)

    result = await db.execute(stmt)
    rows = result.all()

    if not rows:
        raise HTTPException(status_code=404, detail="No availability data")

    # Merge grids across months
    sites: dict[str, dict[str, str]] = {}
    site_names: dict[str, str] = {}  # unit_id → display name
    latest_scraped = None

    for row in rows:
        grid = row.grid or {}

        # Extract the name map if present (ReserveCalifornia stores it as _site_names)
        if "_site_names" in grid:
            site_names.update(grid["_site_names"])

        for site_id, dates in grid.items():
            if site_id.startswith("_"):
                continue  # skip metadata keys
            if site_id not in sites:
                sites[site_id] = {}
            sites[site_id].update(dates)

        if latest_scraped is None or row.scraped_at > latest_scraped:
            latest_scraped = row.scraped_at

    return {
        "facility_id": facility_id,
        "sites": sites,
        "site_names": site_names,
        "last_updated": latest_scraped.isoformat() if latest_scraped else None,
    }
