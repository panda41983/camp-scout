from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import httpx
import pytest
import respx

from campscout.providers.base import Region
from campscout.providers.recreation_gov import (
    AVAILABILITY_BASE,
    RIDB_BASE,
    RecreationGovProvider,
)

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


@pytest.fixture
def provider() -> RecreationGovProvider:
    return RecreationGovProvider(api_key="test-key", user_agent="CampScout/test")


@respx.mock
async def test_list_facilities_paginates(provider: RecreationGovProvider) -> None:
    """Two pages of results, verify all collected and pagination stops."""
    page1 = _load("ridb_facilities_page1.json")
    page2 = _load("ridb_facilities_page2.json")

    respx.get(f"{RIDB_BASE}/facilities").mock(
        side_effect=[
            httpx.Response(200, json=page1),
            httpx.Response(200, json=page2),
        ]
    )

    results = await provider.list_facilities(Region(state="CA"))

    # page1 has 2 valid, page2 has 1 valid + 1 zero-coord (filtered)
    assert len(results) == 3
    assert results[0].external_id == "231958"
    assert results[1].external_id == "232464"
    assert results[2].external_id == "232450"


@respx.mock
async def test_list_facilities_maps_fields(provider: RecreationGovProvider) -> None:
    """Verify FacilityRecord fields are correctly mapped from RIDB JSON."""
    page1 = _load("ridb_facilities_page1.json")
    # Make it a single-page result
    page1["METADATA"]["RESULTS"]["TOTAL_COUNT"] = 2

    respx.get(f"{RIDB_BASE}/facilities").mock(
        return_value=httpx.Response(200, json=page1)
    )

    results = await provider.list_facilities(Region(state="CA"))
    arroyo = results[0]

    assert arroyo.name == "Arroyo Seco Campground"
    assert arroyo.lat == 36.2327
    assert arroyo.lng == -121.4871
    assert arroyo.parent_name == "Los Padres National Forest"
    assert arroyo.state == "CA"
    assert arroyo.provider == "recreation_gov"
    assert arroyo.campsite_count == 49
    assert "recreation.gov" in arroyo.booking_url


@respx.mock
async def test_list_facilities_filters_zero_coords(provider: RecreationGovProvider) -> None:
    """Facilities with 0,0 coordinates are filtered out."""
    page2 = _load("ridb_facilities_page2.json")
    page2["METADATA"]["RESULTS"]["TOTAL_COUNT"] = 2

    respx.get(f"{RIDB_BASE}/facilities").mock(
        return_value=httpx.Response(200, json=page2)
    )

    results = await provider.list_facilities(Region(state="CA"))
    assert len(results) == 1
    assert results[0].external_id == "232450"


@respx.mock
async def test_fetch_availability_parses_grid(provider: RecreationGovProvider) -> None:
    """Verify the availability grid is correctly parsed and statuses normalized."""
    fixture = _load("availability_month.json")

    respx.get(f"{AVAILABILITY_BASE}/232464/month").mock(
        return_value=httpx.Response(200, json=fixture)
    )

    grid = await provider.fetch_availability("232464", date(2026, 6, 1))

    assert "site_001" in grid
    assert "site_002" in grid

    # Check normalized statuses for site_001
    s1 = grid["site_001"]
    assert s1["2026-06-01"] == "reserved"
    assert s1["2026-06-13"] == "available"
    assert s1["2026-06-15"] == "not_reservable"
    assert s1["2026-06-20"] == "available"

    # Check site_002
    s2 = grid["site_002"]
    assert s2["2026-06-01"] == "available"
    assert s2["2026-06-02"] == "not_reservable"
    assert s2["2026-06-15"] == "available"


@respx.mock
async def test_fetch_availability_start_date_format(provider: RecreationGovProvider) -> None:
    """start_date param is always the 1st of month with correct format."""
    respx.get(f"{AVAILABILITY_BASE}/12345/month").mock(
        return_value=httpx.Response(200, json={"campsites": {}})
    )

    await provider.fetch_availability("12345", date(2026, 6, 15))

    req = respx.calls.last.request
    assert "start_date=2026-06-01T00%3A00%3A00.000Z" in str(req.url)


def test_booking_url(provider: RecreationGovProvider) -> None:
    url = provider.booking_url("232464")
    assert url == "https://www.recreation.gov/camping/campgrounds/232464"


@respx.mock
async def test_list_facilities_sends_apikey(provider: RecreationGovProvider) -> None:
    """RIDB requests include the apikey header."""
    page = _load("ridb_facilities_page1.json")
    page["METADATA"]["RESULTS"]["TOTAL_COUNT"] = 2

    respx.get(f"{RIDB_BASE}/facilities").mock(
        return_value=httpx.Response(200, json=page)
    )

    await provider.list_facilities(Region(state="CA"))

    req = respx.calls.last.request
    assert req.headers["apikey"] == "test-key"
    assert req.headers["user-agent"] == "CampScout/test"
