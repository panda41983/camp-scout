from __future__ import annotations

import datetime

from pydantic import BaseModel, field_validator


class CreateWatchRequest(BaseModel):
    name: str | None = None
    facility_id: int  # watch a specific facility
    date_start: datetime.date
    date_end: datetime.date
    nights: int = 1

    @field_validator("nights")
    @classmethod
    def nights_range(cls, v: int) -> int:
        if v < 1 or v > 14:
            raise ValueError("nights must be between 1 and 14")
        return v


class UpdateWatchRequest(BaseModel):
    is_active: bool


class WatchResponse(BaseModel):
    id: int
    name: str | None
    facility_ids: list[int] | None
    date_start: datetime.date
    date_end: datetime.date
    nights: int
    is_active: bool
    created_at: datetime.datetime
