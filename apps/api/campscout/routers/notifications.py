from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from campscout.auth import CurrentUser, get_current_user
from campscout.db import get_db
from campscout.models.facility import Facility
from campscout.models.notification import Notification
from campscout.schemas.notification import NotificationResponse

router = APIRouter(prefix="/api")


@router.get("/notifications", response_model=list[NotificationResponse])
async def list_notifications(
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = Query(default=20, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[NotificationResponse]:
    stmt = (
        select(
            Notification.id,
            Notification.watch_id,
            Notification.available_dates,
            Notification.channel,
            Notification.sent_at,
            Facility.name.label("facility_name"),
            Facility.booking_url,
        )
        .join(Facility, Facility.id == Notification.facility_id)
        .where(Notification.user_id == user.id)
        .order_by(Notification.sent_at.desc())
        .limit(limit)
        .offset(offset)
    )

    result = await db.execute(stmt)
    return [
        NotificationResponse(
            id=row.id,
            watch_id=row.watch_id,
            facility_name=row.facility_name,
            available_dates=row.available_dates,
            channel=row.channel,
            sent_at=row.sent_at,
            booking_url=row.booking_url,
        )
        for row in result.all()
    ]
