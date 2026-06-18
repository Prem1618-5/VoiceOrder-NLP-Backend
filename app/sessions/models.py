"""
SQLAlchemy ORM model for the sessions table.

DB schema (Technical Spec):
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid()
    user_id     UUID REFERENCES users(id)
    status      VARCHAR(20) DEFAULT 'active'   -- active | closed
    turn_count  INT DEFAULT 0
    created_at  TIMESTAMP DEFAULT now()
    expires_at  TIMESTAMP DEFAULT now() + interval '30 min'
"""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active", index=True
    )  # active | closed
    turn_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now() + interval '30 minutes'"),
        nullable=False,
    )

    def __repr__(self) -> str:
        return (
            f"<Session id={self.id} user={self.user_id} "
            f"status={self.status} turns={self.turn_count}>"
        )
