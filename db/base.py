"""
SQLAlchemy 2.0 declarative base.

All ORM models inherit from Base defined here:
  app/auth/models.py       → User
  app/orders/models.py     → MenuItem, Order
  app/sessions/models.py   → Session

This module deliberately imports nothing from app/* to keep the
dependency graph acyclic:
  db.base  ←  all model modules
  db.migrations.env  ←  db.base + all model modules (for Alembic discovery)
"""
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Project-wide SQLAlchemy 2.0 declarative base."""
    pass
