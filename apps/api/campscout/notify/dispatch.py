"""Dispatch notifications to users when new availability is detected."""
from __future__ import annotations

import datetime

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from campscout.models.notification import Notification
from campscout.models.user import User
from campscout.models.watch import Watch
from campscout.notify.dedup import should_send
from campscout.notify.email import send_availability_alert
from campscout.scanner.diff import DiffResult

log = structlog.get_logger()


async def dispatch_notifications(
    session: AsyncSession,
    facility_id: int,
    facility_name: str,
    booking_url: str,
    diff: DiffResult,
) -> int:
    """Find matching watches, dedup, send emails. Returns count of emails sent."""
    # Collect all newly-available dates across all campsites
    new_dates: set[datetime.date] = set()
    campsite_ids: list[str] = []
    for site_id, date_strs in diff.newly_available.items():
        campsite_ids.append(site_id)
        for ds in date_strs:
            new_dates.add(datetime.date.fromisoformat(ds))
    # Locked sites are cancellations about to unlock — also notify
    for site_id, date_strs in diff.newly_locked.items():
        if site_id not in campsite_ids:
            campsite_ids.append(site_id)
        for ds in date_strs:
            new_dates.add(datetime.date.fromisoformat(ds))

    if not new_dates:
        return 0

    min_date = min(new_dates)
    max_date = max(new_dates)

    # Find active watches that cover this facility and overlap the date range
    stmt = (
        select(Watch, User.email, User.notify_email)
        .join(User, User.id == Watch.user_id)
        .where(
            Watch.is_active.is_(True),
            Watch.facility_ids.any(facility_id),
            Watch.date_start <= max_date,
            Watch.date_end >= min_date,
        )
    )
    result = await session.execute(stmt)
    rows = result.all()

    sent_count = 0

    for watch, user_email, notify_email in rows:
        if not notify_email:
            continue

        # Filter dates to those within this watch's range
        watch_dates = sorted(
            d for d in new_dates if watch.date_start <= d <= watch.date_end
        )
        if not watch_dates:
            continue

        # Dedup check
        ok_to_send, dedup_key = await should_send(
            session, watch.id, facility_id, watch_dates
        )
        if not ok_to_send:
            log.info(
                "notification_deduped",
                watch_id=watch.id,
                facility_id=facility_id,
            )
            continue

        # Send email
        success = await send_availability_alert(
            to_email=user_email,
            facility_name=facility_name,
            booking_url=booking_url,
            available_dates=watch_dates,
            watch_name=watch.name,
        )

        if success:
            # Record in notifications table
            notification = Notification(
                watch_id=watch.id,
                user_id=watch.user_id,
                facility_id=facility_id,
                available_dates=watch_dates,
                campsite_external_ids=campsite_ids,
                channel="email",
                dedup_key=dedup_key,
            )
            session.add(notification)
            sent_count += 1

    return sent_count
