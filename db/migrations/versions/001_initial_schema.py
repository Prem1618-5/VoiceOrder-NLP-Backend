"""Initial schema — users, menu_items, sessions, orders.

Revision ID: 001
Revises:
Create Date: 2024-01-01 00:00:00

Tables created (FK-safe order):
  1. users        (no foreign keys)
  2. menu_items   (no foreign keys)
  3. sessions     (FK → users)
  4. orders       (FK → users, sessions)

Indexes per Technical Spec:
  idx_orders_user, idx_orders_session
  idx_sessions_user, idx_sessions_status
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 1. users ──────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("hashed_pw", sa.String(255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
    )
    op.create_index("idx_users_email", "users", ["email"], unique=True)

    # ── 2. menu_items ─────────────────────────────────────────────────────────
    op.create_table(
        "menu_items",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("category", sa.String(100), nullable=True),
        sa.Column("price", sa.Numeric(8, 2), nullable=True),
        sa.Column("modifiers", JSONB, nullable=True),
        sa.Column("tags", JSONB, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("idx_menu_items_name", "menu_items", ["name"])

    # ── 3. sessions ───────────────────────────────────────────────────────────
    op.create_table(
        "sessions",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="active",
        ),
        sa.Column("turn_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now() + interval '30 minutes'"),
            nullable=False,
        ),
    )
    op.create_index("idx_sessions_user", "sessions", ["user_id"])
    op.create_index("idx_sessions_status", "sessions", ["status"])

    # ── 4. orders ─────────────────────────────────────────────────────────────
    op.create_table(
        "orders",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "session_id",
            UUID(as_uuid=True),
            sa.ForeignKey("sessions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("items", JSONB, nullable=False),
        sa.Column("total_price", sa.Numeric(10, 2), nullable=True),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column(
            "for_review",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("idx_orders_user", "orders", ["user_id"])
    op.create_index("idx_orders_session", "orders", ["session_id"])


def downgrade() -> None:
    # Drop in reverse FK order
    op.drop_table("orders")
    op.drop_table("sessions")
    op.drop_table("menu_items")
    op.drop_table("users")
