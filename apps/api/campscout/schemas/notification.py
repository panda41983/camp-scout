from __future__ import annotations

import datetime

from pydantic import BaseModel


class NotificationResponse(BaseModel):
    id: int
    watch_id: int
    facility_name: str
    available_dates: list[datetime.date]
    channel: str
    sent_at: datetime.datetime
    booking_url: str
