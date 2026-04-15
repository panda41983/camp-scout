from __future__ import annotations

from datetime import datetime

from geoalchemy2 import Geography
from sqlalchemy import BigInteger, Enum, ForeignKey, Index, Integer, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from campscout.models import Base

provider_enum = Enum(
    "recreation_gov",
    "reserve_california",
    name="provider",
    create_type=True,
)


class Facility(Base):
    __tablename__ = "facilities"
    __table_args__ = (
        UniqueConstraint("provider", "external_id"),
        Index("facilities_location_gix", "location", postgresql_using="gist"),
        Index("facilities_state_idx", "state"),
        Index(
            "facilities_name_trgm",
            "name",
            postgresql_using="gin",
            postgresql_ops={"name": "gin_trgm_ops"},
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    provider: Mapped[str] = mapped_column(provider_enum, nullable=False)
    external_id: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    parent_name: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    location = mapped_column(Geography(geometry_type="POINT", srid=4326), nullable=True)
    state: Mapped[str | None] = mapped_column(Text)
    nearest_town: Mapped[str | None] = mapped_column(Text)
    campsite_count: Mapped[int | None] = mapped_column(Integer)
    amenities = mapped_column(JSONB, nullable=True)
    photo_url: Mapped[str | None] = mapped_column(Text)
    booking_url: Mapped[str] = mapped_column(Text, nullable=False)
    last_synced_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now()
    )

    campsites: Mapped[list[Campsite]] = relationship(back_populates="facility")


class Campsite(Base):
    __tablename__ = "campsites"
    __table_args__ = (
        UniqueConstraint("facility_id", "external_id"),
        Index("campsites_facility_idx", "facility_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    facility_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("facilities.id", ondelete="CASCADE"), nullable=False
    )
    external_id: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str | None] = mapped_column(Text)
    site_type: Mapped[str | None] = mapped_column(Text)
    attributes = mapped_column(JSONB, nullable=True)

    facility: Mapped[Facility] = relationship(back_populates="campsites")
