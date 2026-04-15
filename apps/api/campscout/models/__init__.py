from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


# Import all models so Base.metadata sees every table.
# These must come after Base is defined to avoid circular imports.
from campscout.models.availability import AvailabilitySnapshot, CurrentAvailability  # noqa: E402, F401
from campscout.models.facility import Campsite, Facility  # noqa: E402, F401
from campscout.models.notification import Notification  # noqa: E402, F401
from campscout.models.scan_job import ScanJob  # noqa: E402, F401
from campscout.models.user import User  # noqa: E402, F401
from campscout.models.watch import Watch  # noqa: E402, F401
