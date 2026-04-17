from __future__ import annotations

from typing import Annotated

import datetime

import structlog
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from campscout.auth import CurrentUser, get_current_user
from campscout.db import get_db
from campscout.models.availability import CurrentAvailability
from campscout.models.facility import Facility
from campscout.models.user import User
from campscout.models.watch import Watch
from campscout.notify.dedup import should_send
from campscout.notify.email import send_availability_alert
from campscout.models.notification import Notification
from campscout.scanner.job_planner import recompute_scan_jobs
from campscout.schemas.watch import CreateWatchRequest, UpdateWatchRequest, WatchResponse

router = APIRouter(prefix="/api")


def _watch_to_response(watch: Watch) -> WatchResponse:
    return WatchResponse(
        id=watch.id,
        name=watch.name,
        facility_ids=watch.facility_ids,
        date_start=watch.date_start,
        date_end=watch.date_end,
        nights=watch.nights,
        is_active=watch.is_active,
        created_at=watch.created_at,
    )


@router.post("/watches", response_model=WatchResponse, status_code=201)
async def create_watch(
    body: CreateWatchRequest,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> WatchResponse:
    watch = Watch(
        user_id=user.id,
        name=body.name,
        facility_ids=[body.facility_id],
        date_start=body.date_start,
        date_end=body.date_end,
        nights=body.nights,
    )
    db.add(watch)
    await db.flush()

    await recompute_scan_jobs(db)

    return _watch_to_response(watch)


@router.get("/watches", response_model=list[WatchResponse])
async def list_watches(
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[WatchResponse]:
    result = await db.execute(
        select(Watch).where(Watch.user_id == user.id).order_by(Watch.created_at.desc())
    )
    watches = result.scalars().all()
    return [_watch_to_response(w) for w in watches]


@router.patch("/watches/{watch_id}", response_model=WatchResponse)
async def update_watch(
    watch_id: int,
    body: UpdateWatchRequest,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> WatchResponse:
    watch = await _get_owned_watch(db, watch_id, user.id)
    watch.is_active = body.is_active
    await db.flush()

    await recompute_scan_jobs(db)

    return _watch_to_response(watch)


@router.delete("/watches/{watch_id}", status_code=204)
async def delete_watch(
    watch_id: int,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    watch = await _get_owned_watch(db, watch_id, user.id)
    await db.delete(watch)
    await db.flush()

    await recompute_scan_jobs(db)


log = structlog.get_logger()


async def _notify_existing_availability(
    db: AsyncSession, watch: Watch, user: CurrentUser
) -> None:
    """If the watched facility already has availability, send an immediate email."""
    try:
        for fid in (watch.facility_ids or []):
            # Check current_availability for matching dates
            result = await db.execute(
                select(CurrentAvailability.available_dates)
                .where(CurrentAvailability.facility_id == fid)
            )
            all_dates: list[datetime.date] = []
            for row in result.all():
                all_dates.extend(row[0] or [])

            # Filter to watch's date range
            matching = sorted(
                d for d in all_dates if watch.date_start <= d <= watch.date_end
            )
            if not matching:
                continue

            # Get facility info
            fac_result = await db.execute(
                select(Facility.name, Facility.booking_url).where(Facility.id == fid)
            )
            fac_row = fac_result.one_or_none()
            if not fac_row:
                continue

            # Dedup check
            ok, dedup_key = await should_send(db, watch.id, fid, matching)
            if not ok:
                continue

            # Send email
            success = await send_availability_alert(
                to_email=user.email,
                facility_name=fac_row.name,
                booking_url=fac_row.booking_url,
                available_dates=matching,
                watch_name=watch.name,
            )

            if success:
                notification = Notification(
                    watch_id=watch.id,
                    user_id=user.id,
                    facility_id=fid,
                    available_dates=matching,
                    channel="email",
                    dedup_key=dedup_key,
                )
                db.add(notification)
                log.info("immediate_notification_sent", watch_id=watch.id, facility_id=fid)
    except Exception:
        log.exception("immediate_notification_failed", watch_id=watch.id)


async def _get_owned_watch(db: AsyncSession, watch_id: int, user_id) -> Watch:
    result = await db.execute(select(Watch).where(Watch.id == watch_id))
    watch = result.scalar_one_or_none()
    if watch is None or watch.user_id != user_id:
        raise HTTPException(status_code=404, detail="Watch not found")
    return watch
