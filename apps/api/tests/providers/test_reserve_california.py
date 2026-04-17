from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import httpx
import pytest
import respx

from campscout.providers.reserve_california import (
    BASE_URL,
    ReserveCaliforniaProvider,
    _extract_date,
    _extract_unit_id,
    _parse_slice_status,
)

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


def _load(name: str) -> dict | list:
    return json.loads((FIXTURES / name).read_text())


@pytest.fixture
def provider() -> ReserveCaliforniaProvider:
    return ReserveCaliforniaProvider(user_agent="CampScout/test", request_delay=0)


# --- Unit helper tests ---

def test_extract_unit_id() -> None:
    assert _extract_unit_id("bucket2.39601") == "39601"
    assert _extract_unit_id("bucket1.39600") == "39600"
    assert _extract_unit_id("bucket99.12345") == "12345"


def test_extract_date() -> None:
    assert _extract_date("2026-06-19T00:00:00") == "2026-06-19"
    assert _extract_date("2026-12-31T00:00:00") == "2026-12-31"


def test_parse_slice_available() -> None:
    assert _parse_slice_status({"IsFree": True, "Lock": None, "IsBlocked": False, "IsWalkin": False, "ReservationId": 0}) == "available"


def test_parse_slice_reserved() -> None:
    assert _parse_slice_status({"IsFree": False, "Lock": None, "IsBlocked": False, "IsWalkin": False, "ReservationId": 7768031}) == "reserved"


def test_parse_slice_locked() -> None:
    assert _parse_slice_status({"IsFree": False, "Lock": "2026-06-22T08:00:00", "IsBlocked": False, "IsWalkin": False, "ReservationId": 0}) == "locked"


def test_parse_slice_blocked() -> None:
    assert _parse_slice_status({"IsFree": False, "Lock": None, "IsBlocked": True, "IsWalkin": False, "ReservationId": 0}) == "not_reservable"


def test_parse_slice_walkin() -> None:
    assert _parse_slice_status({"IsFree": False, "Lock": None, "IsBlocked": False, "IsWalkin": True, "ReservationId": 0}) == "walk_in"


# --- Grid parsing test ---

@respx.mock
async def test_fetch_availability_parses_grid(provider: ReserveCaliforniaProvider) -> None:
    grid_data = _load("rca_grid_response.json")

    respx.post(f"{BASE_URL}/rdr/search/grid").mock(
        return_value=httpx.Response(200, json=grid_data)
    )

    grid = await provider.fetch_availability("406", date(2026, 6, 19))

    # UnitId 39601 from "bucket2.39601"
    assert "39601" in grid
    s = grid["39601"]
    assert s["2026-06-19"] == "available"
    assert s["2026-06-20"] == "reserved"
    assert s["2026-06-21"] == "locked"
    assert s["2026-06-22"] == "not_reservable"
    assert s["2026-06-23"] == "walk_in"

    # UnitId 39600 from "bucket1.39600"
    assert "39600" in grid
    assert grid["39600"]["2026-06-19"] == "reserved"

    # Name map stored under _site_names
    assert "_site_names" in grid
    assert grid["_site_names"]["39601"] == "2"
    assert grid["_site_names"]["39600"] == "1"


# --- Facility discovery deduplication test ---

@respx.mock
async def test_list_facilities_deduplicates_parks(provider: ReserveCaliforniaProvider) -> None:
    parks = _load("rca_citypark_response.json")
    place_response = _load("rca_place_search_response.json")

    # All 26 letter queries return the same 2 parks → should deduplicate
    respx.get(url__startswith=f"{BASE_URL}/rdr/fd/citypark/namecontains/").mock(
        return_value=httpx.Response(200, json=parks)
    )

    # Place search returns facilities for Angel Island
    respx.post(f"{BASE_URL}/rdr/search/place").mock(
        return_value=httpx.Response(200, json=place_response)
    )

    from campscout.providers.base import Region
    results = await provider.list_facilities(Region(state="CA"))

    # 2 parks discovered (deduplicated from 26 letter queries)
    # Each park gets a place search → Angel Island has 2 facilities
    # Anza-Borrego also returns the same fixture → 2 more
    # Total: 4 facilities (2 parks × 2 facilities each)
    assert len(results) == 4
    assert results[0].provider == "reserve_california"
    assert results[0].state == "CA"
    assert "reservecalifornia.com" in results[0].booking_url
    assert results[0].amenities == {"place_id": 614}
