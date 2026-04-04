# =============================================================================
# app/schemas/task.py
#
# PURPOSE:
#   Pydantic schemas for task-related request/response data.
#
# DRF EQUIVALENT:
#   These are DRF Serializers for the Task model.
#   Notice we have separate schemas for Create, Update, and Response —
#   in DRF you might use the same serializer with different read_only/write_only
#   field configs, or separate serializers per use case.
#
# ENUM-STYLE VALIDATION:
#   We use Python's Literal types (or Enum) so Pydantic rejects invalid values
#   at the schema level, before they even reach the service layer.
#   DRF EQUIVALENT: choices= parameter on a serializer field + validate_ method.
#
# PAGINATION:
#   TaskListResponse wraps a list of tasks with pagination metadata —
#   a common production pattern (used by DRF's PageNumberPagination too).
# =============================================================================

from datetime import date, datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums (as Literal types for clean OpenAPI docs)
# ---------------------------------------------------------------------------

TaskStatus = Literal["todo", "in_progress", "done"]
TaskPriority = Literal["low", "medium", "high"]


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class TaskCreate(BaseModel):
    """
    Schema for creating a new task.

    DRF EQUIVALENT:
      class TaskSerializer(serializers.ModelSerializer):
          class Meta:
              model = Task
              fields = ['title', 'description', 'status', 'priority', 'due_date']

    Note: owner_id is NOT here — it comes from the authenticated user (Depends),
    not from the client. This prevents a user from creating tasks for others.
    """
    title: str = Field(
        ...,
        min_length=3,
        max_length=255,
        description="Short task summary",
        examples=["Implement JWT authentication"],
    )
    description: Optional[str] = Field(
        None,
        max_length=2000,
        description="Detailed task description",
        examples=["Create access/refresh token flow using python-jose"],
    )
    status: TaskStatus = Field(
        default="todo",
        description="Current status of the task",
    )
    priority: TaskPriority = Field(
        default="medium",
        description="Task priority level",
    )
    due_date: Optional[date] = Field(
        None,
        description="Optional deadline (YYYY-MM-DD)",
        examples=["2024-12-31"],
    )


class TaskUpdate(BaseModel):
    """
    Schema for updating an existing task (full or partial).

    All fields are Optional — only the provided fields are updated.

    DRF EQUIVALENT: partial=True serializer or a dedicated UpdateSerializer.
    """
    title: Optional[str] = Field(None, min_length=3, max_length=255)
    description: Optional[str] = Field(None, max_length=2000)
    status: Optional[TaskStatus] = None
    priority: Optional[TaskPriority] = None
    due_date: Optional[date] = None
    is_completed: Optional[bool] = None


class TaskFilterParams(BaseModel):
    """
    Query parameter schema for filtering and pagination.

    FastAPI can automatically parse these from the URL query string
    when this is used as a Depends() parameter model.

    DRF EQUIVALENT: DRF FilterSet (django-filter) or a custom list_queryset.
    """
    status: Optional[TaskStatus] = None
    priority: Optional[TaskPriority] = None
    is_completed: Optional[bool] = None
    search: Optional[str] = Field(None, description="Search in title and description")
    page: int = Field(default=1, ge=1, description="Page number (1-indexed)")
    page_size: int = Field(default=10, ge=1, le=100, description="Items per page")


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class TaskResponse(BaseModel):
    """
    Schema for a single task in API responses.

    Includes owner_id so the consumer knows who owns the task,
    but NOT the full owner object (to keep responses slim).

    DRF EQUIVALENT:
      class TaskSerializer(serializers.ModelSerializer):
          class Meta:
              model = Task
              fields = '__all__'
              read_only_fields = ['id', 'owner_id', 'created_at', 'updated_at']
    """
    id: int
    title: str
    description: Optional[str]
    status: str
    priority: str
    is_completed: bool
    due_date: Optional[date]
    owner_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True  # Read from SQLAlchemy ORM objects


class TaskListResponse(BaseModel):
    """
    Paginated list response for tasks.

    Wraps the list with metadata so the client knows how many pages exist.

    DRF EQUIVALENT: PageNumberPagination response format:
      {
        "count": 42,
        "next": "http://api/tasks?page=3",
        "previous": "http://api/tasks?page=1",
        "results": [...]
      }

    We use a slightly richer format with total_pages and current_page.
    """
    tasks: List[TaskResponse]
    total: int           # Total matching records (ignoring pagination)
    page: int            # Current page number
    page_size: int       # Items per page
    total_pages: int     # ceil(total / page_size)
