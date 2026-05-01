"""Create scan_jobs for ALL facilities so the scanner keeps availability fresh.

Runs daily and ~15s after startup. Inserts missing (facility, month) rows with
BULK_INTERVAL_MINUTES, then realigns intervals against active watches so
unwatched rows drift back up to the relaxed default.
"""
from __future__ import annotations

import datetime

import structlog
from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from campscout.models.facility import Facility
from campscout.models.scan_job import ScanJob
from campscout.scanner.job_planner import BULK_INTERVAL_MINUTES, recompute_scan_jobs

log = structlog.get_logger()


SEED_MONTHS_AHEAD = 6  # current month + next 5 = 6 total months of coverage
SEED_COMMIT_BATCH = 100  # commit every N facilities so locks stay short


def _months_to_seed() -> list[datetime.date]:
    today = datetime.date.today()
    cur = today.replace(day=1)
    months = []
    for _ in range(SEED_MONTHS_AHEAD):
        months.append(cur)
        if cur.month == 12:
            cur = cur.replace(year=cur.year + 1, month=1)
        else:
            cur = cur.replace(month=cur.month + 1)
    return months


async def seed_bulk_scan_jobs(session_factory: async_sessionmaker[AsyncSession]) -> int:
    """Ensure every facility has scan_jobs for the next 6 months, then realign intervals.

    Commits per batch of facilities to keep transactions short and avoid blocking
    the scanner. Bumps statement_timeout so a brief lock wait doesn't abort the run.
    """
    months = _months_to_seed()
    log.info("bulk_seed_starting", months=[m.isoformat() for m in months])

    async with session_factory() as session:
        # Supabase defaults statement_timeout to 8s on some roles; loosen for this run
        await session.execute(text("SET LOCAL statement_timeout = '60s'"))

        result = await session.execute(select(Facility.id))
        facility_ids = [row[0] for row in result.all()]

        created = 0
        for i, fid in enumerate(facility_ids):
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

            if (i + 1) % SEED_COMMIT_BATCH == 0:
                await session.commit()
                # SET LOCAL only lasts for the prior tx; reapply for the next one
                await session.execute(text("SET LOCAL statement_timeout = '60s'"))

        await session.commit()

        realigned = await recompute_scan_jobs(session)

    log.info(
        "bulk_scan_jobs_seeded",
        created=created,
        watch_covered=realigned,
        total_facilities=len(facility_ids),
    )
    return created
