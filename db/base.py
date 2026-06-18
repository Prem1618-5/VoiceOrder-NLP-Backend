"""
SQLAlchemy declarative base shared across all models.
All ORM models import Base from here.
"""
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """
    Single declarative base for:
      - app/auth/models.py    → User
      - app/orders/models.py  → MenuItem, Order
      - app/sessions/models.py → Session
    Alembic env.py imports this Base to autogenerate migrations.
    """
    pass
