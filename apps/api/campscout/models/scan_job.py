from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import BigInteger, Date, ForeignKey, Index, Integer, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from campscout.models import Base


class ScanJob(Base):
    __tablename__ = "scan_jobs"
    __table_args__ = (
        UniqueConstraint("facility_id", "month"),
        Index(
            "scan_jobs_due_idx",
            "next_run_at",
            postgresql_where="consecutive_failures < 5",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    facility_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("facilities.id", ondelete="CASCADE"), nullable=False
    )
    month: Mapped[date] = mapped_column(Date, nullable=False)
    interval_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    next_run_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    last_run_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    last_status: Mapped[str | None] = mapped_column(Text)
    consecutive_failures: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
