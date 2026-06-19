"""
SQLAlchemy ORM models for the orders module.

Tables:
  menu_items  — restaurant menu catalogue
  orders      — parsed + persisted order records
"""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Numeric, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class MenuItem(Base):
    """
    DB schema (Technical Spec):
        id          UUID PRIMARY KEY DEFAULT gen_random_uuid()
        name        VARCHAR(255) NOT NULL
        category    VARCHAR(100)
        price       NUMERIC(8,2)
        modifiers   JSONB     -- ["extra cheese", "thin crust"]
        tags        JSONB     -- ["spicy", "vegetarian"]
        created_at  TIMESTAMP DEFAULT now()
    """

    __tablename__ = "menu_items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    price: Mapped[Optional[float]] = mapped_column(Numeric(8, 2), nullable=True)
    modifiers: Mapped[Optional[List[str]]] = mapped_column(JSONB, nullable=True)
    tags: Mapped[Optional[List[str]]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<MenuItem id={self.id} name={self.name} price={self.price}>"


class Order(Base):
    """
    DB schema (Technical Spec):
        id           UUID PRIMARY KEY DEFAULT gen_random_uuid()
        session_id   UUID REFERENCES sessions(id)
        user_id      UUID REFERENCES users(id)
        items        JSONB NOT NULL
        total_price  NUMERIC(10,2)
        status       VARCHAR(20) DEFAULT 'pending'
        confidence   FLOAT
        for_review   BOOLEAN DEFAULT false
        created_at   TIMESTAMP DEFAULT now()
        updated_at   TIMESTAMP DEFAULT now()
    """

    __tablename__ = "orders"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    session_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sessions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    items: Mapped[List[Dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    total_price: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )  # pending | confirmed | cancelled
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    for_review: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return (
            f"<Order id={self.id} user={self.user_id} "
            f"status={self.status} confidence={self.confidence}>"
        )
