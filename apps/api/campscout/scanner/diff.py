"""Compare two availability grids and return what changed.

Pure logic — no DB, no I/O.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from campscout.providers.base import AvailabilityGrid


@dataclass
class DiffResult:
    # campsite_id -> list of date strings that became available
    newly_available: dict[str, list[str]] = field(default_factory=dict)
    # campsite_id -> list of date strings that became unavailable
    newly_unavailable: dict[str, list[str]] = field(default_factory=dict)

    @property
    def has_changes(self) -> bool:
        return bool(self.newly_available or self.newly_unavailable)


def compute_diff(old_grid: AvailabilityGrid, new_grid: AvailabilityGrid) -> DiffResult:
    """Compare old and new grids, return dates that changed to/from 'available'.

    - A date changing to 'available' from anything else → newly_available
    - A date changing from 'available' to anything else → newly_unavailable
    - A site appearing in new but not old → all 'available' dates are newly_available
    - A site in old but not new → ignored (provider may have removed the listing)
    """
    result = DiffResult()

    all_site_ids = set(old_grid.keys()) | set(new_grid.keys())

    for site_id in all_site_ids:
        old_dates = old_grid.get(site_id, {})
        new_dates = new_grid.get(site_id, {})

        # Only care about dates present in the new grid
        if site_id not in new_grid:
            continue

        all_dates = set(old_dates.keys()) | set(new_dates.keys())

        avail_dates: list[str] = []
        unavail_dates: list[str] = []

        for date_str in sorted(all_dates):
            old_status = old_dates.get(date_str, "")
            new_status = new_dates.get(date_str, "")

            if old_status == new_status:
                continue

            if new_status == "available" and old_status != "available":
                avail_dates.append(date_str)
            elif old_status == "available" and new_status != "available":
                unavail_dates.append(date_str)

        if avail_dates:
            result.newly_available[site_id] = avail_dates
        if unavail_dates:
            result.newly_unavailable[site_id] = unavail_dates

    return result
