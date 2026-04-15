"""Manage scan_jobs based on active watches.

The fan-in pattern: multiple watches for the same (facility, month) share one scan job
with interval = min(all watchers' intervals).
"""
from __future__ import annotations

import datetime

from geoalchemy2 import Geography
from sqlalchemy import cast, delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from campscout.models.facility import Facility
from campscout.models.scan_job import ScanJob
from campscout.models.watch import Watch


def _months_for_watch(w_start: datetime.date, w_end: datetime.date) -> list[datetime.date]:
    """Return first-of-month dates spanning [start, end]."""
    months = []
    cur = w_start.replace(day=1)
    while cur <= w_end:
        months.append(cur)
        if cur.month == 12:
            cur = cur.replace(year=cur.year + 1, month=1)
        else:
            cur = cur.replace(month=cur.month + 1)
    return months


async def recompute_scan_jobs(session: AsyncSession) -> int:
    """Recompute all scan_jobs from active watches. Returns count of jobs."""
    # Collect all (facility_id, month) -> min_interval from active watches
    needed: dict[tuple[int, datetime.date], int] = {}

    watches_q = select(Watch).where(Watch.is_active.is_(True))
    result = await session.execute(watches_q)
    watches = result.scalars().all()

    for watch in watches:
        months = _months_for_watch(watch.date_start, watch.date_end)

        if watch.facility_ids:
            # Explicit facility list
            facility_ids = watch.facility_ids
        elif watch.center is not None and watch.radius_meters is not None:
            # Area-based watch — find facilities within radius
            center_point = cast(
                func.ST_MakePoint(
                    func.ST_X(func.geometry(watch.center)),
                    func.ST_Y(func.geometry(watch.center)),
                ),
                Geography,
            )
            fac_q = select(Facility.id).where(
                func.ST_DWithin(Facility.location, center_point, watch.radius_meters)
            )
            fac_result = await session.execute(fac_q)
            facility_ids = [row[0] for row in fac_result.all()]
        else:
            continue

        for fid in facility_ids:
            for month in months:
                key = (fid, month)
                existing = needed.get(key, 999999)
                needed[key] = min(existing, watch.scan_interval_minutes)

    # Upsert scan_jobs
    for (facility_id, month), interval in needed.items():
        stmt = insert(ScanJob).values(
            facility_id=facility_id,
            month=month,
            interval_minutes=interval,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["facility_id", "month"],
            set_={"interval_minutes": interval},
        )
        await session.execute(stmt)

    # Delete scan_jobs that are no longer needed by any watch
    if needed:
        needed_pairs = list(needed.keys())
        # Build a list of (facility_id, month) tuples to keep
        from sqlalchemy import tuple_

        delete_stmt = delete(ScanJob).where(
            ~tuple_(ScanJob.facility_id, ScanJob.month).in_(needed_pairs)
        )
        await session.execute(delete_stmt)
    else:
        # No watches — delete all scan_jobs
        await session.execute(delete(ScanJob))

    await session.commit()
    return len(needed)


async def get_due_jobs(session: AsyncSession, limit: int = 50) -> list[ScanJob]:
    """Return scan_jobs that are due for execution."""
    stmt = (
        select(ScanJob)
        .where(
            ScanJob.next_run_at <= func.now(),
            ScanJob.consecutive_failures < 5,
        )
        .order_by(ScanJob.next_run_at)
        .limit(limit)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())
