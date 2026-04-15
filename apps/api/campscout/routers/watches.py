from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from campscout.auth import CurrentUser, get_current_user
from campscout.db import get_db
from campscout.models.watch import Watch
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


async def _get_owned_watch(db: AsyncSession, watch_id: int, user_id) -> Watch:
    result = await db.execute(select(Watch).where(Watch.id == watch_id))
    watch = result.scalar_one_or_none()
    if watch is None or watch.user_id != user_id:
        raise HTTPException(status_code=404, detail="Watch not found")
    return watch
