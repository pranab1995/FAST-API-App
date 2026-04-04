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

from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Integer, String
from sqlalchemy.orm import relationship

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
    id = Column(Integer, primary_key=True, index=True)

    # ------------------------------------------------------------------
    # Identity fields
    # ------------------------------------------------------------------
    email = Column(
        String(255),
        unique=True,     # No two users share an email
        index=True,      # B-tree index for fast lookup during login
        nullable=False,
    )
    full_name = Column(String(255), nullable=False)

    # ------------------------------------------------------------------
    # Security
    # ------------------------------------------------------------------
    hashed_password = Column(
        String(255),
        nullable=False,
        # NOTE: We store the HASH, never the plain password.
        # The hash includes the bcrypt salt, so it's safe to store as-is.
    )

    # ------------------------------------------------------------------
    # Account status
    # ------------------------------------------------------------------
    is_active = Column(
        Boolean,
        default=True,
        nullable=False,
        # Soft-delete pattern: deactivate instead of delete,
        # preserving referential integrity with tasks.
    )

    # ------------------------------------------------------------------
    # Audit timestamps
    # SQL server-side default: the DB sets these, not Python — avoids
    # clock skew between app servers.
    # ------------------------------------------------------------------
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at = Column(
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
    tasks = relationship(
        "Task",
        back_populates="owner",
        cascade="all, delete-orphan",
        lazy="select",  # Tasks loaded only when accessed (not eager loaded)
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email!r}>"
