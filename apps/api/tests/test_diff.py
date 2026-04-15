from __future__ import annotations

from campscout.scanner.diff import compute_diff


def test_newly_available() -> None:
    old = {"site_1": {"2026-06-13": "reserved", "2026-06-14": "reserved"}}
    new = {"site_1": {"2026-06-13": "available", "2026-06-14": "reserved"}}

    diff = compute_diff(old, new)

    assert diff.newly_available == {"site_1": ["2026-06-13"]}
    assert diff.newly_unavailable == {}
    assert diff.has_changes


def test_newly_unavailable() -> None:
    old = {"site_1": {"2026-06-13": "available"}}
    new = {"site_1": {"2026-06-13": "reserved"}}

    diff = compute_diff(old, new)

    assert diff.newly_available == {}
    assert diff.newly_unavailable == {"site_1": ["2026-06-13"]}


def test_no_change() -> None:
    grid = {
        "site_1": {"2026-06-13": "available", "2026-06-14": "reserved"},
        "site_2": {"2026-06-13": "reserved"},
    }

    diff = compute_diff(grid, grid)

    assert not diff.has_changes
    assert diff.newly_available == {}
    assert diff.newly_unavailable == {}


def test_new_site_appears() -> None:
    old = {}
    new = {"site_1": {"2026-06-13": "available", "2026-06-14": "reserved"}}

    diff = compute_diff(old, new)

    assert diff.newly_available == {"site_1": ["2026-06-13"]}
    assert diff.newly_unavailable == {}


def test_site_removed_from_grid_ignored() -> None:
    old = {"site_1": {"2026-06-13": "available"}}
    new = {}

    diff = compute_diff(old, new)

    # Site removed from grid — not treated as a change
    assert not diff.has_changes


def test_multiple_sites_multiple_changes() -> None:
    old = {
        "site_1": {"2026-06-13": "reserved", "2026-06-14": "available"},
        "site_2": {"2026-06-13": "available"},
    }
    new = {
        "site_1": {"2026-06-13": "available", "2026-06-14": "reserved"},
        "site_2": {"2026-06-13": "available"},
    }

    diff = compute_diff(old, new)

    assert diff.newly_available == {"site_1": ["2026-06-13"]}
    assert diff.newly_unavailable == {"site_1": ["2026-06-14"]}


def test_status_change_between_non_available() -> None:
    """Changes between non-available statuses (e.g., reserved -> closed) are not tracked."""
    old = {"site_1": {"2026-06-13": "reserved"}}
    new = {"site_1": {"2026-06-13": "closed"}}

    diff = compute_diff(old, new)

    assert not diff.has_changes
