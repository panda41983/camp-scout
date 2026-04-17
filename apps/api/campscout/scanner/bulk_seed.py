"""Create scan_jobs for ALL facilities so the scanner keeps availability fresh.

Runs daily. Creates jobs for current month + next month with a relaxed interval
(60 min vs 15 min for watched facilities). Watched facilities keep their shorter
intervals since recompute_scan_jobs uses min(interval).
"""
from __future__ import annotations

import datetime

import structlog
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from campscout.models.facility import Facility
from campscout.models.scan_job import ScanJob

log = structlog.get_logger()

BULK_INTERVAL_MINUTES = 60  # relaxed interval for bulk scanning


def _current_and_next_month() -> list[datetime.date]:
    today = datetime.date.today()
    current = today.replace(day=1)
    if current.month == 12:
        next_m = current.replace(year=current.year + 1, month=1)
    else:
        next_m = current.replace(month=current.month + 1)
    return [current, next_m]


async def seed_bulk_scan_jobs(session_factory: async_sessionmaker[AsyncSession]) -> int:
    """Ensure every facility has scan_jobs for current + next month. Returns jobs created."""
    months = _current_and_next_month()

    async with session_factory() as session:
        # Get all facility IDs
        result = await session.execute(select(Facility.id))
        facility_ids = [row[0] for row in result.all()]

        created = 0
        for fid in facility_ids:
            for month in months:
                stmt = insert(ScanJob).values(
                    facility_id=fid,
                    month=month,
                    interval_minutes=BULK_INTERVAL_MINUTES,
                )
                # Don't overwrite existing jobs (watches may have shorter intervals)
                stmt = stmt.on_conflict_do_nothing(index_elements=["facility_id", "month"])
                result = await session.execute(stmt)
                if result.rowcount > 0:
                    created += 1

        await session.commit()

    log.info("bulk_scan_jobs_seeded", created=created, total_facilities=len(facility_ids))
    return created
