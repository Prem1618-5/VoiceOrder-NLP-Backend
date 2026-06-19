"""
SQLAlchemy ORM model for the `users` table.
Uses SQLAlchemy 2.0 declarative mapping with typed columns.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class User(Base):
    """
    DB schema (from Technical Spec):
        id          UUID PRIMARY KEY DEFAULT gen_random_uuid()
        email       VARCHAR(255) UNIQUE NOT NULL
        hashed_pw   VARCHAR(255) NOT NULL
        created_at  TIMESTAMP DEFAULT now()
        is_active   BOOLEAN DEFAULT true
    """

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )
    hashed_pw: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email} active={self.is_active}>"
