from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from campscout.models import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    email: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    phone: Mapped[str | None] = mapped_column(Text)
    notify_email: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    notify_sms: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
