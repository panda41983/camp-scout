from __future__ import annotations

import datetime

from sqlalchemy import BigInteger, Date, ForeignKey, Index, PrimaryKeyConstraint, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from campscout.models import Base


class AvailabilitySnapshot(Base):
    __tablename__ = "availability_snapshots"
    __table_args__ = (
        Index(
            "snapshots_facility_month_idx",
            "facility_id",
            "month",
            "scraped_at",
            postgresql_using="btree",
            postgresql_ops={"scraped_at": "DESC"},
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    facility_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("facilities.id", ondelete="CASCADE"), nullable=False
    )
    scraped_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    month: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    grid = mapped_column(JSONB, nullable=False)


class CurrentAvailability(Base):
    __tablename__ = "current_availability"
    __table_args__ = (
        PrimaryKeyConstraint("facility_id", "month"),
        Index("current_avail_dates_gin", "available_dates", postgresql_using="gin"),
    )

    facility_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("facilities.id", ondelete="CASCADE"), nullable=False
    )
    month: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    scraped_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False
    )
    grid = mapped_column(JSONB, nullable=False)
    available_dates = mapped_column(ARRAY(Date), nullable=False)
