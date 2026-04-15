from __future__ import annotations

import datetime

from pydantic import BaseModel, field_validator


class LatLng(BaseModel):
    lat: float
    lng: float

    @field_validator("lat")
    @classmethod
    def lat_range(cls, v: float) -> float:
        if not -90 <= v <= 90:
            raise ValueError("lat must be between -90 and 90")
        return v

    @field_validator("lng")
    @classmethod
    def lng_range(cls, v: float) -> float:
        if not -180 <= v <= 180:
            raise ValueError("lng must be between -180 and 180")
        return v


class SearchRequest(BaseModel):
    center: LatLng
    radius_miles: float
    date_start: datetime.date
    date_end: datetime.date
    nights: int = 1

    @field_validator("radius_miles")
    @classmethod
    def radius_positive(cls, v: float) -> float:
        if v <= 0 or v > 200:
            raise ValueError("radius_miles must be between 0 and 200")
        return v

    @field_validator("nights")
    @classmethod
    def nights_range(cls, v: int) -> int:
        if v < 1 or v > 14:
            raise ValueError("nights must be between 1 and 14")
        return v


class FacilityResult(BaseModel):
    id: int
    name: str
    parent_name: str | None
    lat: float
    lng: float
    available_dates: list[datetime.date]
    booking_url: str
    last_updated: datetime.datetime


class SearchResponse(BaseModel):
    results: list[FacilityResult]
    total: int
