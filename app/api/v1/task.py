# =============================================================================
# app/api/v1/task.py
#
# PURPOSE:
#   HTTP layer for task CRUD endpoints.
#   All routes are protected — only authenticated users can access them.
#   Business logic is entirely in TaskService; this file only handles
#   HTTP in/out and dependency wiring.
#
# ⭐ DRF EQUIVALENT:
#   This file = DRF ModelViewSet (or a set of APIViews)
#
#   DRF TaskViewSet would have:
#     list()     → GET  /tasks/
#     create()   → POST /tasks/
#     retrieve() → GET  /tasks/{id}/
#     update()   → PUT  /tasks/{id}/
#     partial_update() → PATCH /tasks/{id}/
#     destroy()  → DELETE /tasks/{id}/
#
#   FastAPI uses individual decorated functions instead of class methods,
#   but the HTTP contract is identical.
#
# QUERY PARAMETERS vs REQUEST BODY:
#   POST/PUT/PATCH → request body (JSON) → validated by Pydantic schema
#   GET list       → query parameters   → also validated by Pydantic via Query()
#
#   DRF uses request.query_params for filtering; we use FastAPI's Query() params.
#
# PAGINATION:
#   Clients control page and page_size via query params.
#   The response always includes total, page, page_size, total_pages.
# =============================================================================

from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_active_user, get_db
from app.models.user import User
from app.schemas.task import TaskCreate, TaskListResponse, TaskResponse, TaskUpdate
from app.services.task_service import TaskService

router = APIRouter()


# =============================================================================
# Task CRUD endpoints
# All routes require a valid JWT — enforced by Depends(get_current_active_user)
# =============================================================================

@router.post(
    "/",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new task",
    description="Create a task owned by the currently authenticated user.",
)
def create_task(
    data: TaskCreate,                                     # Request body (JSON)
    db: Session = Depends(get_db),                        # DB session
    current_user: User = Depends(get_current_active_user),# Authenticated user
):
    """
    Create a task.

    The owner_id is set automatically from the JWT — the client cannot
    specify whose task this is. This is the ownership enforcement pattern.

    DRF EQUIVALENT:
      def perform_create(self, serializer):
          serializer.save(owner=self.request.user)
    """
    task = TaskService.create_task(db=db, data=data, current_user=current_user)
    return task


@router.get(
    "/",
    response_model=TaskListResponse,
    summary="List tasks with filtering and pagination",
    description=(
        "Return a paginated list of the current user's tasks. "
        "Supports filtering by status, priority, and completion status, "
        "plus a full-text search across title and description."
    ),
)
def list_tasks(
    # ------------------------------------------------------------------
    # Query parameters — FastAPI reads these from the URL automatically.
    # e.g. GET /tasks/?status=todo&priority=high&page=2&page_size=5
    #
    # DRF EQUIVALENT:
    #   filter_backends = [DjangoFilterBackend, SearchFilter]
    #   filterset_fields = ['status', 'priority', 'is_completed']
    #   search_fields = ['title', 'description']
    #   pagination_class = PageNumberPagination
    # ------------------------------------------------------------------
    status: Optional[str] = Query(
        None,
        description="Filter by status: todo | in_progress | done",
        pattern="^(todo|in_progress|done)$",
    ),
    priority: Optional[str] = Query(
        None,
        description="Filter by priority: low | medium | high",
        pattern="^(low|medium|high)$",
    ),
    is_completed: Optional[bool] = Query(
        None,
        description="Filter by completion status: true or false",
    ),
    search: Optional[str] = Query(
        None,
        description="Search in title and description (case-insensitive)",
        max_length=200,
    ),
    page: int = Query(default=1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(default=10, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    List tasks with optional filtering, search, and pagination.

    Example requests:
      GET /api/v1/tasks/?page=1&page_size=10
      GET /api/v1/tasks/?status=todo&priority=high
      GET /api/v1/tasks/?search=authentication&page=2
    """
    return TaskService.list_tasks(
        db=db,
        current_user=current_user,
        status=status,
        priority=priority,
        is_completed=is_completed,
        search=search,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{task_id}",
    response_model=TaskResponse,
    summary="Get a specific task",
)
def get_task(
    task_id: int,                                         # Path parameter
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Retrieve a single task by ID.

    Returns 404 if the task doesn't exist OR doesn't belong to the current user.
    This prevents information leakage about other users' task IDs.

    DRF EQUIVALENT:
      def get_object(self):
          obj = get_object_or_404(Task, pk=pk, owner=self.request.user)
          self.check_object_permissions(self.request, obj)
          return obj
    """
    return TaskService.get_task(db=db, task_id=task_id, current_user=current_user)


@router.patch(
    "/{task_id}",
    response_model=TaskResponse,
    summary="Update a task (partial)",
    description="Update one or more fields of a task. Unspecified fields remain unchanged.",
)
def update_task(
    task_id: int,
    data: TaskUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Partially update a task.

    Uses PATCH semantics — only the fields provided in the request body are updated.
    Sending {"is_completed": true} will also auto-set status to "done".

    DRF EQUIVALENT:
      def partial_update(self, request, *args, **kwargs):
          kwargs['partial'] = True
          return self.update(request, *args, **kwargs)
    """
    return TaskService.update_task(
        db=db,
        task_id=task_id,
        data=data,
        current_user=current_user,
    )


@router.delete(
    "/{task_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete a task",
    description="Permanently delete a task. This action cannot be undone.",
)
def delete_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Delete a task permanently.

    Returns 200 with a message. Alternatively, 204 No Content is also RESTful
    but 200 with a message provides better feedback to API consumers.

    DRF EQUIVALENT:
      def destroy(self, request, *args, **kwargs):
          instance = self.get_object()
          self.perform_destroy(instance)
          return Response(status=status.HTTP_204_NO_CONTENT)
    """
    return TaskService.delete_task(
        db=db,
        task_id=task_id,
        current_user=current_user,
    )
