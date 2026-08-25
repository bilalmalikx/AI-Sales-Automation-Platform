"""
SQLAlchemy declarative base and common model mixins.

All ORM models inherit from Base.
"""

import uuid
from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""

    # Disable implicit table name generation — all models must explicitly
    # declare __tablename__
    __abstract__ = True


class TimestampMixin:
    """Mixin adding created_at and updated_at columns."""

    created_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow,
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow,
        server_default=func.now(),
        onupdate=datetime.utcnow,
        server_onupdate=func.now(),
        nullable=False,
    )


class UUIDPrimaryKeyMixin:
    """Mixin adding a UUID primary key column."""

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )


def repr_helper(obj: object, *attrs: str) -> str:
    """Helper to build a clean __repr__ for models."""
    cls_name = obj.__class__.__name__
    attr_strs = [f"{a}={getattr(obj, a)!r}" for a in attrs if hasattr(obj, a)]
    return f"{cls_name}({', '.join(attr_strs)})"
