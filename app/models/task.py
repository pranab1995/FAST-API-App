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

from datetime import date, datetime, timezone

from sqlalchemy import (
    Boolean, Column, Date, DateTime, ForeignKey,
    Integer, String, Text,
)
from sqlalchemy.orm import relationship

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
    id = Column(Integer, primary_key=True, index=True)

    # ------------------------------------------------------------------
    # Content
    # ------------------------------------------------------------------
    title = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)

    # ------------------------------------------------------------------
    # Status & Priority
    # ------------------------------------------------------------------
    # Store as strings; the service layer validates against allowed values.
    # Possible values: "todo" | "in_progress" | "done"
    status = Column(String(50), default="todo", nullable=False, index=True)

    # Possible values: "low" | "medium" | "high"
    priority = Column(String(50), default="medium", nullable=False, index=True)

    # ------------------------------------------------------------------
    # Soft-delete flag (allows "archive" UX without losing data)
    # ------------------------------------------------------------------
    is_completed = Column(Boolean, default=False, nullable=False)

    # ------------------------------------------------------------------
    # Deadline
    # ------------------------------------------------------------------
    due_date = Column(Date, nullable=True)

    # ------------------------------------------------------------------
    # Audit timestamps
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
    # Foreign key — ownership
    # ------------------------------------------------------------------
    # ForeignKey creates a DB-level constraint: owner_id MUST reference
    # a valid user id. The DB will reject orphaned tasks automatically.
    #
    # DRF EQUIVALENT:
    #   owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="tasks")
    # ------------------------------------------------------------------
    owner_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,  # Index for fast "fetch tasks by user" queries
    )

    # ------------------------------------------------------------------
    # Relationship back to User
    # ------------------------------------------------------------------
    # back_populates="tasks" must match the attribute name on the User model.
    # This allows: task.owner → User object (no extra query if loaded)
    # ------------------------------------------------------------------
    owner = relationship("User", back_populates="tasks")

    def __repr__(self) -> str:
        return f"<Task id={self.id} title={self.title!r} owner_id={self.owner_id}>"
