# =============================================================================
# app/models/task.py
#
# PURPOSE:
#   SQLAlchemy ORM model for the tasks table.
#   Represents a to-do task owned by a user.
#
# DRF EQUIVALENT:
#   Same as Django's models.Model. The ForeignKey here maps to Django's
#   ForeignKey(User, on_delete=models.CASCADE).
#
# DESIGN NOTES:
#   - Priority is stored as a String with a CHECK constraint (via Enum).
#     In a large project you'd use a PostgreSQL ENUM type or a separate
#     priorities lookup table.
#   - Status follows the same pattern.
#   - due_date is nullable — tasks may not always have a deadline.
# =============================================================================

from typing import Optional, TYPE_CHECKING
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, Date, DateTime, ForeignKey,
    Integer, String, Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from app.models.user import User

from app.db.base import Base


class Task(Base):
    """
    Represents a task (to-do item) in the system.

    Each task belongs to exactly one user.
    Table: tasks
    """
    __tablename__ = "tasks"

    # ------------------------------------------------------------------
    # Primary key
    # ------------------------------------------------------------------
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # ------------------------------------------------------------------
    # Content
    # ------------------------------------------------------------------
    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # ------------------------------------------------------------------
    # Status & Priority
    # ------------------------------------------------------------------
    status: Mapped[str] = mapped_column(String(50), default="todo", nullable=False, index=True)
    priority: Mapped[str] = mapped_column(String(50), default="medium", nullable=False, index=True)

    # ------------------------------------------------------------------
    # Soft-delete flag
    # ------------------------------------------------------------------
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # ------------------------------------------------------------------
    # Deadline
    # ------------------------------------------------------------------
    due_date: Mapped[Optional[datetime]] = mapped_column(Date, nullable=True)  # type: ignore[assignment]

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
    # Foreign key — ownership
    # ------------------------------------------------------------------
    owner_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ------------------------------------------------------------------
    # Relationship back to User
    # ------------------------------------------------------------------
    # back_populates="tasks" must match the attribute name on the User model.
    # This allows: task.owner → User object (no extra query if loaded)
    # ------------------------------------------------------------------
    owner: Mapped["User"] = relationship("User", back_populates="tasks")

    def __repr__(self) -> str:
        return f"<Task id={self.id} title={self.title!r} owner_id={self.owner_id}>"
