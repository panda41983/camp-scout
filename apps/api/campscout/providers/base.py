from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import date
from typing import Literal, Protocol, runtime_checkable

ProviderName = Literal["recreation_gov", "reserve_california"]

# {campsite_external_id: {date_iso_str: status}}
# status: "available" | "reserved" | "not_reservable" | "closed" | "locked" | "walk_in"
AvailabilityGrid = dict[str, dict[str, str]]


@dataclass
class FacilityRecord:
    external_id: str
    name: str
    lat: float
    lng: float
    provider: ProviderName
    parent_name: str | None = None
    description: str | None = None
    state: str | None = None
    nearest_town: str | None = None
    campsite_count: int | None = None
    amenities: dict | None = None
    photo_url: str | None = None
    booking_url: str = ""


@dataclass
class Region:
    state: str


# Global concurrency cap per provider — limits outbound HTTP.
MAX_CONCURRENT_REQUESTS = 10
request_semaphore: asyncio.Semaphore = field(
    default_factory=lambda: asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
)


def get_semaphore() -> asyncio.Semaphore:
    """Return the global request semaphore. Lazy-init to avoid event loop issues."""
    global _semaphore
    try:
        return _semaphore
    except NameError:
        _semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
        return _semaphore


@runtime_checkable
class Provider(Protocol):
    name: ProviderName

    async def list_facilities(self, region: Region) -> list[FacilityRecord]: ...

    async def fetch_availability(
        self, facility_external_id: str, month: date
    ) -> AvailabilityGrid: ...

    def booking_url(self, facility_external_id: str) -> str: ...
