"""Scanner runner — fetches availability for due jobs, stores snapshots, computes diffs."""
from __future__ import annotations

import datetime

import structlog
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from campscout.models.availability import AvailabilitySnapshot, CurrentAvailability
from campscout.models.facility import Facility
from campscout.models.scan_job import ScanJob
from campscout.providers.base import AvailabilityGrid, Provider
from campscout.scanner.diff import compute_diff
from campscout.scanner.job_planner import get_due_jobs

log = structlog.get_logger()

MAX_BACKOFF_MINUTES = 240  # 4 hours


def _extract_available_dates(grid: AvailabilityGrid) -> list[datetime.date]:
    """From a grid, return sorted dates where ANY site has status 'available'."""
    dates: set[datetime.date] = set()
    for site_dates in grid.values():
        for date_str, status in site_dates.items():
            if status == "available":
                dates.add(datetime.date.fromisoformat(date_str))
    return sorted(dates)


async def _get_previous_grid(
    session: AsyncSession, facility_id: int, month: datetime.date
) -> AvailabilityGrid | None:
    """Fetch the most recent successful snapshot grid for diff comparison."""
    stmt = (
        select(AvailabilitySnapshot.grid)
        .where(
            AvailabilitySnapshot.facility_id == facility_id,
            AvailabilitySnapshot.month == month,
        )
        .order_by(AvailabilitySnapshot.scraped_at.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    row = result.scalar_one_or_none()
    return row


async def _process_job(
    session: AsyncSession, job: ScanJob, provider: Provider
) -> None:
    """Fetch availability for one job, store snapshot, update current, compute diff."""
    # Look up the facility's external_id
    fac_q = select(Facility.external_id).where(Facility.id == job.facility_id)
    fac_result = await session.execute(fac_q)
    external_id = fac_result.scalar_one_or_none()

    if external_id is None:
        log.warning("scan_job_orphaned", job_id=job.id, facility_id=job.facility_id)
        return

    try:
        grid = await provider.fetch_availability(external_id, job.month)
    except Exception:
        # Increment failures, apply exponential backoff
        new_failures = job.consecutive_failures + 1
        backoff = min(job.interval_minutes * (2 ** new_failures), MAX_BACKOFF_MINUTES)
        job.consecutive_failures = new_failures
        job.last_status = "error"
        job.next_run_at = func.now() + datetime.timedelta(minutes=backoff)
        log.exception(
            "scan_job_failed",
            job_id=job.id,
            facility_id=job.facility_id,
            external_id=external_id,
            consecutive_failures=new_failures,
        )
        return

    now = datetime.datetime.now(tz=datetime.UTC)

    # Store snapshot
    snapshot = AvailabilitySnapshot(
        facility_id=job.facility_id,
        month=job.month,
        scraped_at=now,
        grid=grid,
    )
    session.add(snapshot)

    # Upsert current_availability
    available_dates = _extract_available_dates(grid)
    ca_stmt = insert(CurrentAvailability).values(
        facility_id=job.facility_id,
        month=job.month,
        scraped_at=now,
        grid=grid,
        available_dates=available_dates,
    )
    ca_stmt = ca_stmt.on_conflict_do_update(
        index_elements=["facility_id", "month"],
        set_={
            "scraped_at": now,
            "grid": grid,
            "available_dates": available_dates,
        },
    )
    await session.execute(ca_stmt)

    # Compute diff against previous snapshot
    old_grid = await _get_previous_grid(session, job.facility_id, job.month)
    if old_grid is not None:
        diff = compute_diff(old_grid, grid)
        if diff.has_changes:
            log.info(
                "availability_diff",
                facility_id=job.facility_id,
                external_id=external_id,
                newly_available_sites=len(diff.newly_available),
                newly_unavailable_sites=len(diff.newly_unavailable),
            )

    # Update the job
    job.last_run_at = now
    job.last_status = "ok"
    job.consecutive_failures = 0
    job.next_run_at = now + datetime.timedelta(minutes=job.interval_minutes)

    log.info(
        "scan_job_complete",
        job_id=job.id,
        facility_id=job.facility_id,
        external_id=external_id,
        available_date_count=len(available_dates),
    )


async def run_scan_cycle(
    session_factory: async_sessionmaker[AsyncSession],
    provider: Provider,
) -> int:
    """Run one scan cycle: pull due jobs, scrape, store, diff. Returns jobs processed."""
    async with session_factory() as session:
        jobs = await get_due_jobs(session)

        if not jobs:
            return 0

        log.info("scan_cycle_starting", job_count=len(jobs))

        for job in jobs:
            await _process_job(session, job, provider)

        await session.commit()

    log.info("scan_cycle_complete", job_count=len(jobs))
    return len(jobs)
