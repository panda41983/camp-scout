"""Notification deduplication — prevent sending the same alert twice within an hour."""
from __future__ import annotations

import datetime
import hashlib

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from campscout.models.notification import Notification


def compute_dedup_key(watch_id: int, facility_id: int, dates: list[datetime.date]) -> str:
    """Hash (watch_id, facility_id, sorted dates) into a dedup key."""
    sorted_dates = sorted(d.isoformat() for d in dates)
    raw = f"{watch_id}:{facility_id}:{','.join(sorted_dates)}"
    return hashlib.sha256(raw.encode()).hexdigest()


async def should_send(
    session: AsyncSession,
    watch_id: int,
    facility_id: int,
    dates: list[datetime.date],
) -> tuple[bool, str]:
    """Check if this notification was already sent in the last hour.

    Returns (should_send, dedup_key).
    """
    dedup_key = compute_dedup_key(watch_id, facility_id, dates)

    one_hour_ago = datetime.datetime.now(tz=datetime.UTC) - datetime.timedelta(hours=1)
    stmt = select(Notification.id).where(
        Notification.dedup_key == dedup_key,
        Notification.sent_at > one_hour_ago,
    ).limit(1)

    result = await session.execute(stmt)
    already_sent = result.scalar_one_or_none() is not None

    return (not already_sent, dedup_key)
