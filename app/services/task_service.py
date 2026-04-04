# =============================================================================
# app/services/task_service.py
#
# PURPOSE:
#   Business logic layer for all task operations.
#   Orchestrates between the HTTP layer (router) and the DB layer (repo).
#
# DRF EQUIVALENT:
#   DRF typically puts this logic in:
#     - perform_create() / perform_update() in APIView subclasses
#     - Serializer.validate() / Serializer.create() / Serializer.update()
#     - Model Manager methods (objects.create(), custom managers)
#
#   Our service layer is a CLEANER separation — the router only handles
#   HTTP concerns, the repo only handles DB queries, and this file handles
#   the "what should happen" logic independently of both.
#
# KEY BUSINESS RULES IN THIS FILE:
#   1. Ownership enforcement: users can only manage their own tasks
#   2. Auto-status update: marking complete → status becomes "done"
#   3. Pagination metadata calculation (total_pages)
#   4. 404 raising when task not found (repo returns None; we raise HTTP exc)
#
# ⭐ REQUEST FLOW (complete end-to-end):
#
#   HTTP Request
#       ↓
#   FastAPI Router (app/api/v1/task.py)
#       ↓ validates request body via Pydantic Schema (TaskCreate)
#       ↓ injects db and current_user via Depends()
#       ↓
#   TaskService (THIS FILE)
#       ↓ applies business rules
#       ↓ calls repository methods
#       ↓
#   TaskRepository (app/repositories/task_repo.py)
#       ↓ executes SQLAlchemy query
#       ↓
#   PostgreSQL Database
#       ↓
#   ORM model instance (Task)
#       ↓ flows back up through service
#       ↓
#   Router serializes with TaskResponse (Pydantic schema)
#       ↓
#   HTTP Response (JSON)
#
#   DRF EQUIVALENT FLOW:
#   HTTP Request → URL conf → APIView → Serializer validation →
#   perform_create()/perform_update() → Model.save() → DB →
#   Serializer.to_representation() → JSON Response
# =============================================================================

import math
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.task import Task
from app.models.user import User
from app.repositories.task_repo import TaskRepository
from app.schemas.task import TaskCreate, TaskListResponse, TaskResponse, TaskUpdate


class TaskService:
    """
    Business logic for task CRUD and listing operations.

    All methods receive `current_user` — this ensures every operation
    is scoped to the authenticated user at the SERVICE level (not just DB level).
    """

    @staticmethod
    def create_task(db: Session, data: TaskCreate, current_user: User) -> Task:
        """
        Create a new task for the authenticated user.

        Business rules:
          1. owner_id is ALWAYS set from current_user — never from the request
          2. All other fields come from the validated TaskCreate schema

        DRF EQUIVALENT:
          def perform_create(self, serializer):
              serializer.save(owner=self.request.user)

          The key insight: request.user → current_user (via Depends)
          serializer.save() → TaskRepository.create()
        """
        task = TaskRepository.create(
            db=db,
            owner_id=current_user.id,  # ← NEVER from request body
            title=data.title,
            description=data.description,
            status=data.status,
            priority=data.priority,
            due_date=data.due_date,
        )
        return task

    @staticmethod
    def get_task(db: Session, task_id: int, current_user: User) -> Task:
        """
        Fetch a single task by ID, scoped to the current user.

        If the task doesn't belong to current_user, the repo returns None
        (because of the owner_id filter), and we raise a 404. We use 404
        instead of 403 to avoid leaking whether the task ID exists at all
        (IDOR protection).

        DRF EQUIVALENT:
          def get_queryset(self):
              return Task.objects.filter(owner=self.request.user)
          # get_object() then does a get(pk=pk) on this queryset → auto 404
        """
        task = TaskRepository.get_by_id(db, task_id, current_user.id)
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Task with id={task_id} not found",
            )
        return task

    @staticmethod
    def list_tasks(
        db: Session,
        current_user: User,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        is_completed: Optional[bool] = None,
        search: Optional[str] = None,
        page: int = 1,
        page_size: int = 10,
    ) -> TaskListResponse:
        """
        Return a paginated, filtered list of tasks for the current user.

        This method:
          1. Delegates filtering and pagination to the repository
          2. Computes pagination metadata (total_pages)
          3. Returns a structured TaskListResponse schema object

        DRF EQUIVALENT:
          class TaskListView(ListAPIView):
              serializer_class = TaskSerializer
              filter_backends = [DjangoFilterBackend, SearchFilter]
              filterset_fields = ['status', 'priority', 'is_completed']
              search_fields = ['title', 'description']
              pagination_class = PageNumberPagination
        """
        tasks, total = TaskRepository.get_all_for_user(
            db=db,
            owner_id=current_user.id,
            status=status,
            priority=priority,
            is_completed=is_completed,
            search=search,
            page=page,
            page_size=page_size,
        )

        # Calculate total pages
        total_pages = math.ceil(total / page_size) if total > 0 else 0

        return TaskListResponse(
            tasks=[TaskResponse.model_validate(task) for task in tasks],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    @staticmethod
    def update_task(
        db: Session,
        task_id: int,
        data: TaskUpdate,
        current_user: User,
    ) -> Task:
        """
        Update a task's fields (partial update).

        Business rules:
          1. Task must exist and belong to current_user → 404 otherwise
          2. Only non-None fields in the request are updated
          3. Auto-business rule: if is_completed=True → set status="done"
             (status being "done" is the natural state for completed tasks)

        DRF EQUIVALENT:
          def update(self, request, *args, **kwargs):
              partial = True  # PATCH support
              instance = self.get_object()  # auto 404 + permission check
              serializer = self.get_serializer(instance, data=request.data, partial=partial)
              serializer.is_valid(raise_exception=True)
              self.perform_update(serializer)
        """
        # Verify ownership (raises 404 if not found or not owned)
        task = TaskService.get_task(db, task_id, current_user)

        # Build update dict — exclude None fields (partial update)
        update_data = data.model_dump(exclude_none=True)

        # Business rule: completing a task auto-sets status to "done"
        if update_data.get("is_completed") is True:
            update_data.setdefault("status", "done")

        # Business rule: if status is set back to not-done, un-complete it
        if update_data.get("status") in ("todo", "in_progress"):
            update_data.setdefault("is_completed", False)

        task = TaskRepository.update(db, task, update_data)
        return task

    @staticmethod
    def delete_task(db: Session, task_id: int, current_user: User) -> dict:
        """
        Delete a task permanently.

        Business rules:
          1. Task must exist and belong to current_user → 404 otherwise
          2. Returns a success message (no body for 204 would also be valid)

        DRF EQUIVALENT:
          def destroy(self, request, *args, **kwargs):
              instance = self.get_object()   # auto 404 + permission check
              self.perform_destroy(instance) # instance.delete()
              return Response(status=204)
        """
        task = TaskService.get_task(db, task_id, current_user)
        TaskRepository.delete(db, task)
        return {"message": f"Task '{task.title}' deleted successfully"}
