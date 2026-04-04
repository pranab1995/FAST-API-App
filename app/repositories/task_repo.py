# =============================================================================
# app/repositories/task_repo.py
#
# PURPOSE:
#   Data access layer for Task records.
#   Handles all raw SQL/ORM operations for tasks, including:
#     - Single task lookups
#     - Filtered, paginated list queries
#     - Create / update / delete operations
#
# DRF EQUIVALENT:
#   In DRF, this logic typically lives in get_queryset() of a ViewSet,
#   or in a Manager attached to the Django model (e.g., Task.objects.for_user()).
#
#   The repository pattern extracts this into a dedicated class so that:
#     - The service layer never writes raw queries
#     - The API router never touches the DB directly
#     - The query logic is reusable across different services
#
# KEY DESIGN — User-scoped queries:
#   EVERY query filters by owner_id (the authenticated user's ID).
#   This is the database-level enforcement of "users see only their tasks".
#   Even if the service layer has a bug, a user can never see another
#   user's tasks because the DB query always includes:
#       .filter(Task.owner_id == user_id)
# =============================================================================

from typing import List, Optional, Tuple

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.task import Task


class TaskRepository:
    """
    Data access layer for the Task model.

    All methods are scoped to the owning user — security at the DB layer.
    """

    @staticmethod
    def get_by_id(
        db: Session,
        task_id: int,
        owner_id: int,
    ) -> Optional[Task]:
        """
        Fetch a single task by ID, ensuring it belongs to the requesting user.

        The `owner_id` filter is CRITICAL — without it, any authenticated
        user could fetch any task by guessing an ID (IDOR vulnerability).

        DRF EQUIVALENT: get_object() in GenericAPIView with a queryset
        filtered by request.user (via get_queryset).
        """
        return (
            db.query(Task)
            .filter(Task.id == task_id, Task.owner_id == owner_id)
            .first()
        )

    @staticmethod
    def get_all_for_user(
        db: Session,
        owner_id: int,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        is_completed: Optional[bool] = None,
        search: Optional[str] = None,
        page: int = 1,
        page_size: int = 10,
    ) -> Tuple[List[Task], int]:
        """
        Return a paginated, filtered list of tasks for a user.

        Returns a tuple: (list_of_tasks, total_count)
        The total count is returned BEFORE pagination so the caller can
        compute total_pages without a separate query.

        DRF EQUIVALENT:
          - Filtering: django-filter FilterSet or get_queryset() building
          - Pagination: PageNumberPagination (page_size, count from Paginator)
          - Search: SearchFilter backend

        QUERY BUILDING PATTERN:
          We start with a base query and chain .filter() conditions.
          SQLAlchemy is lazy — no SQL is executed until .all() or .count().
          This lets us build complex queries conditionally without string
          concatenation or raw SQL.
        """
        # Base query — always scoped to this user
        query = db.query(Task).filter(Task.owner_id == owner_id)

        # ------------------------------------------------------------------
        # Optional filters — each is only applied if the client provided it
        # ------------------------------------------------------------------
        if status is not None:
            query = query.filter(Task.status == status)

        if priority is not None:
            query = query.filter(Task.priority == priority)

        if is_completed is not None:
            query = query.filter(Task.is_completed == is_completed)

        if search:
            # Full-text search across title and description (case-insensitive)
            # In production you'd use PostgreSQL's full-text search (tsvector)
            # or a dedicated search service (Elasticsearch).
            search_pattern = f"%{search}%"
            query = query.filter(
                or_(
                    Task.title.ilike(search_pattern),
                    Task.description.ilike(search_pattern),
                )
            )

        # ------------------------------------------------------------------
        # Count before pagination (for metadata)
        # ------------------------------------------------------------------
        # This is a separate COUNT(*) query — necessary because .count()
        # after .offset()/.limit() would count only the paginated slice.
        total = query.count()

        # ------------------------------------------------------------------
        # Pagination — OFFSET/LIMIT pattern
        # ------------------------------------------------------------------
        # Page 1 → offset 0, Page 2 → offset page_size, etc.
        offset = (page - 1) * page_size
        tasks = (
            query
            .order_by(Task.created_at.desc())  # Newest first
            .offset(offset)
            .limit(page_size)
            .all()
        )

        return tasks, total

    @staticmethod
    def create(
        db: Session,
        owner_id: int,
        title: str,
        description: Optional[str],
        status: str,
        priority: str,
        due_date: Optional[object],
    ) -> Task:
        """
        Create and persist a new task.

        owner_id is set HERE (from the authenticated user), not from the
        request body — this is the "force ownership" pattern.

        DRF EQUIVALENT:
          serializer.save(owner=self.request.user) in a CreateAPIView.
        """
        task = Task(
            owner_id=owner_id,
            title=title,
            description=description,
            status=status,
            priority=priority,
            due_date=due_date,
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        return task

    @staticmethod
    def update(db: Session, task: Task, update_data: dict) -> Task:
        """
        Apply partial updates to a task and persist.

        Only fields present in update_data are changed (partial update).
        If is_completed is set to True, the service layer may also update
        the status to "done" — that logic lives in task_service.py.
        """
        for field, value in update_data.items():
            setattr(task, field, value)
        db.commit()
        db.refresh(task)
        return task

    @staticmethod
    def delete(db: Session, task: Task) -> None:
        """
        Hard-delete a task from the database.

        Because of the CASCADE on the FK, deleting the owner user also
        deletes all their tasks — this method handles explicit task deletion.
        """
        db.delete(task)
        db.commit()
