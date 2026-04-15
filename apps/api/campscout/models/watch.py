from __future__ import annotations

import uuid
from datetime import date, datetime

from geoalchemy2 import Geography
from sqlalchemy import BigInteger, Boolean, CheckConstraint, Date, ForeignKey, Index, Integer, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from campscout.models import Base


class Watch(Base):
    __tablename__ = "watches"
    __table_args__ = (
        CheckConstraint(
            "(facility_ids IS NOT NULL AND array_length(facility_ids, 1) > 0) "
            "OR (center IS NOT NULL AND radius_meters IS NOT NULL)",
            name="watches_target_check",
        ),
        Index("watches_active_idx", "is_active", postgresql_where="is_active"),
        Index("watches_user_idx", "user_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str | None] = mapped_column(Text)
    facility_ids = mapped_column(ARRAY(BigInteger), nullable=True)
    center = mapped_column(Geography(geometry_type="POINT", srid=4326), nullable=True)
    radius_meters: Mapped[int | None] = mapped_column(Integer)
    date_start: Mapped[date] = mapped_column(Date, nullable=False)
    date_end: Mapped[date] = mapped_column(Date, nullable=False)
    nights: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    flexible: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    weekdays = mapped_column(ARRAY(Integer), nullable=True)
    site_filters = mapped_column(JSONB, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    scan_interval_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="15"
    )
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    expires_at: Mapped[datetime | None] = mapped_column(nullable=True)
