"""ReserveCalifornia provider — Tyler Technologies API (post-Oct 2025)."""
from __future__ import annotations

import asyncio
import calendar
from datetime import date, timedelta

import httpx
import structlog

from campscout.providers.base import AvailabilityGrid, FacilityRecord, ProviderName, Region

log = structlog.get_logger()

BASE_URL = "https://california-rdr.prod.cali.rd12.recreation-management.tylerapp.com"
REQUEST_DELAY = 2.0


def _parse_slice_status(s: dict) -> str:
    """Map a Tyler API slice to our canonical status string."""
    if s.get("IsBlocked"):
        return "not_reservable"
    if s.get("IsWalkin"):
        return "walk_in"
    if s.get("Lock") is not None:
        return "locked"
    if s.get("IsFree"):
        return "available"
    if s.get("ReservationId", 0) > 0:
        return "reserved"
    return "closed"


def _extract_unit_id(bucket_key: str) -> str:
    """Extract UnitId from 'bucket2.39601' → '39601'."""
    parts = bucket_key.split(".")
    return parts[1] if len(parts) == 2 else bucket_key


def _extract_date(slice_key: str) -> str:
    """Extract date from '2026-06-19T00:00:00' → '2026-06-19'."""
    return slice_key[:10]


def _week_chunks(month: date) -> list[tuple[date, date]]:
    """Split a month into 7-day chunks for the Tyler API."""
    start = month.replace(day=1)
    last_day = calendar.monthrange(start.year, start.month)[1]
    end_of_month = start.replace(day=last_day)

    chunks = []
    cur = start
    while cur <= end_of_month:
        chunk_end = min(cur + timedelta(days=6), end_of_month)
        chunks.append((cur, chunk_end))
        cur = chunk_end + timedelta(days=1)
    return chunks


class ReserveCaliforniaProvider:
    name: ProviderName = "reserve_california"

    def __init__(self, user_agent: str, request_delay: float = REQUEST_DELAY) -> None:
        self._request_delay = request_delay
        self._semaphore = asyncio.Semaphore(1)
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0),
            headers={
                "tenantid": "cali",
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": user_agent,
            },
        )

    async def _get(self, path: str) -> dict:
        async with self._semaphore:
            resp = await self._client.get(f"{BASE_URL}{path}")
            resp.raise_for_status()
            await asyncio.sleep(self._request_delay)
            return resp.json()

    async def _post(self, path: str, body: dict) -> dict:
        async with self._semaphore:
            resp = await self._client.post(f"{BASE_URL}{path}", json=body)
            resp.raise_for_status()
            await asyncio.sleep(self._request_delay)
            return resp.json()

    async def list_facilities(self, region: Region) -> list[FacilityRecord]:
        """Discover all parks via alphabet search, then fetch facilities per park."""
        # Step 1: discover parks by iterating a-z
        parks: dict[int, dict] = {}  # PlaceId → park data

        for letter in "abcdefghijklmnopqrstuvwxyz":
            try:
                data = await self._get(f"/rdr/fd/citypark/namecontains/{letter}")
                items = data if isinstance(data, list) else data.get("items", data.get("Items", []))
                if isinstance(items, list):
                    for park in items:
                        place_id = park.get("PlaceId") or park.get("placeId") or 0
                        # Skip cities (PlaceId=0) and entries without coordinates
                        if place_id > 0 and place_id not in parks:
                            parks[place_id] = park
                log.info(
                    "rca_parks_discovered",
                    letter=letter,
                    new_parks=len([p for p in (items if isinstance(items, list) else [])
                                   if (p.get("PlaceId") or p.get("placeId")) not in parks]),
                    total_parks=len(parks),
                )
            except httpx.HTTPStatusError as exc:
                log.warning("rca_park_search_failed", letter=letter, status=exc.response.status_code)
            except Exception:
                log.exception("rca_park_search_error", letter=letter)

        log.info("rca_park_discovery_complete", total_parks=len(parks))

        # Step 2: for each park, fetch facilities
        facilities: list[FacilityRecord] = []
        park_list = list(parks.items())

        for i, (place_id, park) in enumerate(park_list):
            park_name = park.get("Name") or park.get("name") or str(place_id)
            park_lat = park.get("Latitude") or park.get("latitude") or 0.0
            park_lng = park.get("Longitude") or park.get("longitude") or 0.0

            try:
                data = await self._post("/rdr/search/place", {
                    "PlaceId": place_id,
                    "Latitude": park_lat,
                    "Longitude": park_lng,
                    "Nights": 1,
                    "CustomerId": 0,
                    "StartDate": date.today().isoformat(),
                    "UnitCategoryId": 1,
                    "SleepingUnitId": 0,
                    "MinVehicleLength": 0,
                    "UnitTypesGroupIds": [],
                    "AmenityIds": [],
                    "Sort": "distance",
                    "IsADA": False,
                    "RestrictADA": False,
                    "NearbyLimit": 0,
                    "isSearchAllParks": False,
                    "customerClassificationId": 0,
                    "InSeasonOnly": False,
                    "WebOnly": True,
                    "NearbyCountLimit": 0,
                    "NearbyOnlyAvailable": False,
                    "CountNearby": False,
                    "CountUnits": True,
                    "HighlightedPlaceId": 0,
                })

                # The response may have SelectedPlace.Facilities or similar structure
                selected = data.get("SelectedPlace") or data.get("selectedPlace") or {}
                fac_raw = selected.get("Facilities") or selected.get("facilities") or {}
                # Facilities can be a dict keyed by ID or a list
                fac_list = fac_raw.values() if isinstance(fac_raw, dict) else fac_raw

                for fac in fac_list:
                    fac_id = str(fac.get("FacilityId") or fac.get("facilityId") or "")
                    fac_name = fac.get("Name") or fac.get("name") or ""
                    fac_lat = fac.get("Latitude") or fac.get("latitude") or park_lat
                    fac_lng = fac.get("Longitude") or fac.get("longitude") or park_lng

                    if not fac_id:
                        continue

                    facilities.append(FacilityRecord(
                        external_id=fac_id,
                        name=fac_name,
                        lat=float(fac_lat),
                        lng=float(fac_lng),
                        provider="reserve_california",
                        parent_name=park_name,
                        state="CA",
                        campsite_count=fac.get("UnitCount") or fac.get("unitCount"),
                        booking_url=f"https://www.reservecalifornia.com/park/{place_id}/{fac_id}",
                        amenities={"place_id": place_id},
                    ))

                log.info(
                    "rca_park_facilities_fetched",
                    park=park_name,
                    facility_count=len(fac_raw),
                    progress=f"{i + 1}/{len(park_list)}",
                )
            except httpx.HTTPStatusError as exc:
                log.warning("rca_place_search_failed", place_id=place_id, status=exc.response.status_code)
            except Exception:
                log.exception("rca_place_search_error", place_id=place_id)

        return facilities

    async def fetch_availability(
        self, facility_external_id: str, month: date
    ) -> AvailabilityGrid:
        """Fetch availability for a facility for one month (multiple 7-day requests)."""
        grid: AvailabilityGrid = {}

        for chunk_start, chunk_end in _week_chunks(month):
            try:
                data = await self._post("/rdr/search/grid", {
                    "FacilityId": facility_external_id,
                    "UnitSort": "availability",
                    "StartDate": chunk_start.isoformat(),
                    "EndDate": chunk_end.isoformat(),
                    "InSeasonOnly": True,
                    "WebOnly": True,
                    "IsADA": False,
                    "RestrictADA": False,
                    "UnitCategoryId": 1,
                    "SleepingUnitId": 0,
                    "MinVehicleLength": 0,
                    "UnitTypesGroupIds": [],
                    "AmenityIds": [],
                    "CustomerId": 0,
                    "customerClassificationId": 0,
                })

                facility_data = data.get("Facility") or data.get("facility") or {}
                units = facility_data.get("Units") or facility_data.get("units") or {}

                for bucket_key, unit_data in units.items():
                    unit_id = _extract_unit_id(bucket_key)
                    slices = unit_data.get("Slices") or unit_data.get("slices") or {}

                    if unit_id not in grid:
                        grid[unit_id] = {}

                    for slice_key, slice_data in slices.items():
                        day_str = _extract_date(slice_key)
                        grid[unit_id][day_str] = _parse_slice_status(slice_data)

            except httpx.HTTPStatusError as exc:
                log.warning(
                    "rca_grid_fetch_failed",
                    facility_id=facility_external_id,
                    chunk=f"{chunk_start}–{chunk_end}",
                    status=exc.response.status_code,
                )
            except Exception:
                log.exception(
                    "rca_grid_fetch_error",
                    facility_id=facility_external_id,
                    chunk=f"{chunk_start}–{chunk_end}",
                )

        return grid

    def booking_url(self, facility_external_id: str) -> str:
        # Actual URL needs PlaceId — pre-computed during seeding and stored on the row
        return ""

    async def aclose(self) -> None:
        await self._client.aclose()
