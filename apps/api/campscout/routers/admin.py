"""Admin endpoints for ops visibility."""
from __future__ import annotations

import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from campscout.db import get_db
from campscout.models.scan_job import ScanJob

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/scanner-status")
async def scanner_status(db: AsyncSession = Depends(get_db)) -> dict:
    now = datetime.datetime.now(tz=datetime.UTC)

    # Total active jobs (not dead)
    total_q = select(func.count()).select_from(ScanJob).where(ScanJob.consecutive_failures < 5)
    total_active = (await db.execute(total_q)).scalar_one()

    # Overdue jobs (due but not yet run)
    overdue_q = (
        select(func.count())
        .select_from(ScanJob)
        .where(ScanJob.next_run_at <= now, ScanJob.consecutive_failures < 5)
    )
    overdue = (await db.execute(overdue_q)).scalar_one()

    # Jobs with at least one failure
    failing_q = (
        select(func.count()).select_from(ScanJob).where(ScanJob.consecutive_failures > 0)
    )
    failing = (await db.execute(failing_q)).scalar_one()

    # Last 10 completed jobs
    recent_q = (
        select(
            ScanJob.facility_id,
            ScanJob.month,
            ScanJob.last_run_at,
            ScanJob.last_status,
            ScanJob.interval_minutes,
            ScanJob.consecutive_failures,
        )
        .where(ScanJob.last_run_at.is_not(None))
        .order_by(ScanJob.last_run_at.desc())
        .limit(10)
    )
    recent_rows = (await db.execute(recent_q)).all()

    recent_completions = [
        {
            "facility_id": row.facility_id,
            "month": str(row.month),
            "last_run_at": row.last_run_at.isoformat() if row.last_run_at else None,
            "last_status": row.last_status,
            "interval_minutes": row.interval_minutes,
            "consecutive_failures": row.consecutive_failures,
        }
        for row in recent_rows
    ]

    return {
        "total_active_jobs": total_active,
        "overdue_jobs": overdue,
        "failing_jobs": failing,
        "recent_completions": recent_completions,
    }
