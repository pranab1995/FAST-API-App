# =============================================================================
# app/models/user.py
#
# PURPOSE:
#   SQLAlchemy ORM model for the users table.
#   This is the Python representation of the DB schema — changes here
#   are picked up by Alembic to generate migration scripts.
#
# DRF EQUIVALENT:
#   This is Django's models.Model — the class defines the table columns,
#   types, constraints, and relationships.
#
#   Key differences from Django:
#     - Column types are explicit (String, Boolean, DateTime vs CharField)
#     - Relationships use relationship() + ForeignKey explicitly
#     - No built-in UserManager — password hashing is done in the service layer
#     - No AbstractUser to extend; you define everything yourself
#
# RELATIONSHIP:
#   User → Tasks is a one-to-many relationship.
#   One user can have many tasks; each task belongs to exactly one user.
#   SQLAlchemy's relationship() + back_populates creates the bidirectional link.
# =============================================================================

from typing import TYPE_CHECKING
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from app.models.task import Task

from app.db.base import Base


class User(Base):
    """
    Represents a registered user in the system.

    Table: users
    """
    __tablename__ = "users"

    # ------------------------------------------------------------------
    # Primary key
    # ------------------------------------------------------------------
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # ------------------------------------------------------------------
    # Identity fields
    # ------------------------------------------------------------------
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,     # No two users share an email
        index=True,      # B-tree index for fast lookup during login
        nullable=False,
    )
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)

    # ------------------------------------------------------------------
    # Security
    # ------------------------------------------------------------------
    hashed_password: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    # ------------------------------------------------------------------
    # Account status
    # ------------------------------------------------------------------
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    # ------------------------------------------------------------------
    # Audit timestamps
    # ------------------------------------------------------------------
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # ------------------------------------------------------------------
    # Relationships
    # ------------------------------------------------------------------
    # relationship() tells SQLAlchemy how to JOIN users ↔ tasks.
    # "back_populates" creates a bidirectional link:
    #   user.tasks  → list of Task objects belonging to this user
    #   task.owner  → the User object that owns the task
    #
    # cascade="all, delete-orphan": if a user is deleted,
    # all their tasks are automatically deleted too (referential integrity).
    #
    # DRF EQUIVALENT:
    #   This is like Django's ForeignKey with related_name="tasks".
    #   task_set (Django's default) becomes tasks here via back_populates.
    # ------------------------------------------------------------------
    tasks: Mapped[list["Task"]] = relationship(  # type: ignore[name-defined]
        "Task",
        back_populates="owner",
        cascade="all, delete-orphan",
        lazy="select",
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email!r}>"
