from __future__ import annotations

import asyncio
from datetime import date

import httpx
import structlog

from campscout.providers.base import (
    AvailabilityGrid,
    FacilityRecord,
    ProviderName,
    Region,
    get_semaphore,
)

log = structlog.get_logger()

RIDB_BASE = "https://ridb.recreation.gov/api/v1"
AVAILABILITY_BASE = "https://www.recreation.gov/api/camps/availability/campground"
CAMPING_ACTIVITY_ID = "9"
PAGE_SIZE = 50
# Stay well under 50 req/min RIDB limit
REQUEST_DELAY = 1.2


def _normalize_status(raw: str) -> str:
    """Normalize Recreation.gov availability status to our canonical values."""
    lower = raw.lower()
    if lower == "available" or lower == "open":
        return "available"
    if lower == "reserved":
        return "reserved"
    if "not reservable" in lower or "not available" in lower or "nyr" in lower:
        return "not_reservable"
    return "closed"


class RecreationGovProvider:
    name: ProviderName = "recreation_gov"

    def __init__(self, api_key: str, user_agent: str) -> None:
        self._api_key = api_key
        self._user_agent = user_agent
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0),
            headers={"User-Agent": user_agent},
        )

    async def list_facilities(self, region: Region) -> list[FacilityRecord]:
        """Page through all camping facilities in a region via RIDB."""
        facilities: list[FacilityRecord] = []
        offset = 0

        while True:
            async with get_semaphore():
                resp = await self._client.get(
                    f"{RIDB_BASE}/facilities",
                    params={
                        "state": region.state,
                        "activity": CAMPING_ACTIVITY_ID,
                        "limit": PAGE_SIZE,
                        "offset": offset,
                    },
                    headers={"apikey": self._api_key},
                )
                resp.raise_for_status()

            data = resp.json()
            rec_data = data.get("RECDATA", [])
            total_count = data.get("METADATA", {}).get("RESULTS", {}).get("TOTAL_COUNT", 0)

            for raw in rec_data:
                record = self._parse_facility(raw, default_state=region.state)
                if record is not None:
                    facilities.append(record)

            offset += PAGE_SIZE
            log.info(
                "ridb_page_fetched",
                state=region.state,
                offset=offset,
                page_count=len(rec_data),
                total_so_far=len(facilities),
                total_count=total_count,
            )

            if offset >= total_count or len(rec_data) == 0:
                break

            await asyncio.sleep(REQUEST_DELAY)

        return facilities

    async def fetch_availability(
        self, facility_external_id: str, month: date
    ) -> AvailabilityGrid:
        """Fetch the availability grid for a facility for one month."""
        start_date = month.replace(day=1)
        start_str = f"{start_date.isoformat()}T00:00:00.000Z"

        async with get_semaphore():
            resp = await self._client.get(
                f"{AVAILABILITY_BASE}/{facility_external_id}/month",
                params={"start_date": start_str},
            )
            resp.raise_for_status()

        data = resp.json()
        grid: AvailabilityGrid = {}

        for site_id, site_data in data.get("campsites", {}).items():
            site_grid: dict[str, str] = {}
            for date_str, status in site_data.get("availabilities", {}).items():
                # Dates come as "2026-06-01T00:00:00Z" — normalize to "2026-06-01"
                day_str = date_str[:10]
                site_grid[day_str] = _normalize_status(status)
            grid[site_id] = site_grid

        return grid

    def booking_url(self, facility_external_id: str) -> str:
        return f"https://www.recreation.gov/camping/campgrounds/{facility_external_id}"

    def _parse_facility(
        self, raw: dict, default_state: str | None = None
    ) -> FacilityRecord | None:
        """Parse a RIDB facility JSON object into a FacilityRecord."""
        lat = raw.get("FacilityLatitude", 0.0)
        lng = raw.get("FacilityLongitude", 0.0)

        # Skip facilities with missing/zero coordinates
        if lat == 0.0 and lng == 0.0:
            return None

        external_id = str(raw["FacilityID"])

        # Extract state from address array, fall back to region state
        state = None
        for addr in raw.get("FACILITYADDRESS", []):
            s = addr.get("AddressStateCode")
            if s:
                state = s
                break
        if state is None:
            state = default_state

        return FacilityRecord(
            external_id=external_id,
            name=raw.get("FacilityName", ""),
            lat=lat,
            lng=lng,
            provider="recreation_gov",
            parent_name=raw.get("ParentRecAreaName"),
            description=raw.get("FacilityDescription"),
            state=state,
            campsite_count=raw.get("Campsites"),
            photo_url=raw.get("FacilityMapURL"),
            booking_url=self.booking_url(external_id),
        )

    async def aclose(self) -> None:
        await self._client.aclose()
