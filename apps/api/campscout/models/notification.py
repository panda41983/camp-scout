from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Date, ForeignKey, Index, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from campscout.models import Base


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        Index("notifications_watch_idx", "watch_id", "sent_at", postgresql_ops={"sent_at": "DESC"}),
        Index("notifications_dedup_idx", "dedup_key", "sent_at", postgresql_ops={"sent_at": "DESC"}),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    watch_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("watches.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    facility_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("facilities.id"), nullable=False
    )
    available_dates = mapped_column(ARRAY(Date), nullable=False)
    campsite_external_ids = mapped_column(ARRAY(Text), nullable=True)
    channel: Mapped[str] = mapped_column(Text, nullable=False)
    sent_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    dedup_key: Mapped[str] = mapped_column(Text, nullable=False)
