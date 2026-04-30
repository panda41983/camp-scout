"""Create scan_jobs for ALL facilities so the scanner keeps availability fresh.

Runs daily and once on startup. Inserts missing (facility, month) rows with
BULK_INTERVAL_MINUTES, then realigns intervals against active watches so
unwatched rows drift back up to the relaxed default.
"""
from __future__ import annotations

import datetime

import structlog
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from campscout.models.facility import Facility
from campscout.models.scan_job import ScanJob
from campscout.scanner.job_planner import BULK_INTERVAL_MINUTES, recompute_scan_jobs

log = structlog.get_logger()


def _current_and_next_month() -> list[datetime.date]:
    today = datetime.date.today()
    current = today.replace(day=1)
    if current.month == 12:
        next_m = current.replace(year=current.year + 1, month=1)
    else:
        next_m = current.replace(month=current.month + 1)
    return [current, next_m]


async def seed_bulk_scan_jobs(session_factory: async_sessionmaker[AsyncSession]) -> int:
    """Ensure every facility has scan_jobs for current + next month, then realign intervals."""
    months = _current_and_next_month()

    async with session_factory() as session:
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
                stmt = stmt.on_conflict_do_nothing(index_elements=["facility_id", "month"])
                result = await session.execute(stmt)
                if result.rowcount > 0:
                    created += 1

        await session.commit()

        realigned = await recompute_scan_jobs(session)

    log.info(
        "bulk_scan_jobs_seeded",
        created=created,
        watch_covered=realigned,
        total_facilities=len(facility_ids),
    )
    return created
