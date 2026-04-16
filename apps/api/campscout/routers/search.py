from __future__ import annotations

import datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from geoalchemy2 import Geography
from sqlalchemy import cast, func, select, type_coerce
from sqlalchemy.dialects.postgresql import ARRAY, array
from sqlalchemy.types import Date
from sqlalchemy.ext.asyncio import AsyncSession

from campscout.db import get_db
from campscout.models.availability import CurrentAvailability
from campscout.models.facility import Facility
from campscout.schemas.search import FacilityResult, SearchRequest, SearchResponse, SoldOutFacility

router = APIRouter(prefix="/api")

MILES_TO_METERS = 1609.344


def _months_in_range(start: datetime.date, end: datetime.date) -> list[datetime.date]:
    """Return the first-of-month dates spanning [start, end]."""
    months = []
    cur = start.replace(day=1)
    while cur <= end:
        months.append(cur)
        if cur.month == 12:
            cur = cur.replace(year=cur.year + 1, month=1)
        else:
            cur = cur.replace(month=cur.month + 1)
    return months


def _dates_in_range(start: datetime.date, end: datetime.date) -> list[datetime.date]:
    """Return all dates in [start, end]."""
    count = (end - start).days + 1
    return [start + datetime.timedelta(days=i) for i in range(count)]


def _has_contiguous_nights(
    available: list[datetime.date], nights: int, start: datetime.date, end: datetime.date
) -> list[datetime.date]:
    """Filter to dates in range with N contiguous available nights starting on that date."""
    available_set = set(available)
    result = []
    for d in sorted(available_set):
        if d < start or d > end:
            continue
        # Check if d, d+1, ..., d+nights-1 are all available and within range
        span = [d + datetime.timedelta(days=i) for i in range(nights)]
        if span[-1] > end:
            continue
        if all(s in available_set for s in span):
            result.append(d)
    return result


@router.post("/search", response_model=SearchResponse)
async def search(
    body: SearchRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SearchResponse:
    radius_meters = body.radius_miles * MILES_TO_METERS
    months = _months_in_range(body.date_start, body.date_end)
    target_dates = _dates_in_range(body.date_start, body.date_end)

    # Build the point for ST_DWithin — ST_MakePoint(lng, lat)
    center_point = cast(
        func.ST_MakePoint(body.center.lng, body.center.lat), Geography
    )

    stmt = (
        select(
            Facility.id,
            Facility.name,
            Facility.parent_name,
            Facility.provider,
            func.ST_Y(func.geometry(Facility.location)).label("lat"),
            func.ST_X(func.geometry(Facility.location)).label("lng"),
            Facility.booking_url,
            CurrentAvailability.available_dates,
            CurrentAvailability.scraped_at,
        )
        .join(
            CurrentAvailability,
            CurrentAvailability.facility_id == Facility.id,
        )
        .where(
            func.ST_DWithin(Facility.location, center_point, radius_meters),
            CurrentAvailability.month.in_(months),
            CurrentAvailability.available_dates.overlap(
                type_coerce(target_dates, ARRAY(Date))
            ),
        )
    )

    result = await db.execute(stmt)
    rows = result.all()

    # Post-filter: contiguity check for nights > 1, and merge across months
    facility_map: dict[int, FacilityResult] = {}

    for row in rows:
        fid = row.id
        # Filter available_dates to only those in the requested range
        row_dates = [d for d in row.available_dates if body.date_start <= d <= body.date_end]

        if fid in facility_map:
            # Merge dates from another month
            existing = facility_map[fid]
            merged = sorted(set(existing.available_dates + row_dates))
            facility_map[fid] = existing.model_copy(
                update={
                    "available_dates": merged,
                    "last_updated": max(existing.last_updated, row.scraped_at),
                }
            )
        else:
            facility_map[fid] = FacilityResult(
                id=fid,
                name=row.name,
                parent_name=row.parent_name,
                provider=row.provider,
                lat=row.lat,
                lng=row.lng,
                available_dates=sorted(row_dates),
                booking_url=row.booking_url,
                last_updated=row.scraped_at,
            )

    # Apply contiguity filter if nights > 1
    results = []
    for fr in facility_map.values():
        if body.nights > 1:
            contiguous = _has_contiguous_nights(
                fr.available_dates, body.nights, body.date_start, body.date_end
            )
            if not contiguous:
                continue
            fr = fr.model_copy(update={"available_dates": contiguous})
        results.append(fr)

    # Sort by number of available dates, descending
    results.sort(key=lambda r: len(r.available_dates), reverse=True)

    # Query for ALL facilities in the radius that are NOT in the available results
    available_ids = {fr.id for fr in results}

    sold_out_stmt = (
        select(
            Facility.id,
            Facility.name,
            Facility.parent_name,
            Facility.provider,
            func.ST_Y(func.geometry(Facility.location)).label("lat"),
            func.ST_X(func.geometry(Facility.location)).label("lng"),
            Facility.booking_url,
        )
        .where(
            func.ST_DWithin(Facility.location, center_point, radius_meters),
        )
    )

    if available_ids:
        sold_out_stmt = sold_out_stmt.where(Facility.id.notin_(available_ids))

    sold_out_stmt = sold_out_stmt.order_by(Facility.name)

    sold_out_result = await db.execute(sold_out_stmt)
    sold_out = [
        SoldOutFacility(
            id=row.id,
            name=row.name,
            parent_name=row.parent_name,
            provider=row.provider,
            lat=row.lat,
            lng=row.lng,
            booking_url=row.booking_url,
        )
        for row in sold_out_result.all()
    ]

    return SearchResponse(
        results=results,
        sold_out=sold_out,
        total=len(results) + len(sold_out),
    )
