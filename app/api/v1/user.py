# =============================================================================
# app/api/v1/user.py
#
# PURPOSE:
#   HTTP layer for user-related endpoints.
#   Routes define the API contract (HTTP method, path, status codes).
#   They do NOT contain business logic — they delegate to UserService.
#
# ⭐ DRF EQUIVALENT:
#   This file = DRF ViewSet or APIView subclasses
#
#   DRF:
#     class UserViewSet(viewsets.ModelViewSet):
#         serializer_class = UserSerializer
#         permission_classes = [IsAuthenticated]
#
#   FastAPI:
#     @router.post("/register", response_model=UserResponse)
#     def register(data: UserCreate, db: Session = Depends(get_db)):
#         ...
#
#   Key differences:
#     - FastAPI uses function-based routes (not class-based views by default)
#     - Permissions are explicit Depends() declarations, not class attributes
#     - Response schemas (response_model) are declared on the decorator
#
# DRF EQUIVALENT TABLE:
#   POST   /register  → CreateAPIView (no auth)
#   POST   /login     → TokenObtainPairView (simplejwt)
#   POST   /refresh   → TokenRefreshView (simplejwt)
#   GET    /me        → RetrieveAPIView + IsAuthenticated
#   PATCH  /me        → UpdateAPIView  + IsAuthenticated + partial=True
#   POST   /me/change-password → Custom APIView + IsAuthenticated
#   DELETE /me        → DestroyAPIView + IsAuthenticated (soft delete)
#
# ROUTER vs MAIN APP:
#   We use APIRouter (not the main FastAPI app) so this module is
#   "pluggable" — imported and mounted in main.py with a prefix.
#
#   DRF EQUIVALENT: urls.py using include() + router.urls:
#     urlpatterns = [path('api/v1/users/', include('users.urls'))]
# =============================================================================

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_active_user, get_db
from app.models.user import User
from app.schemas.user import (
    PasswordChange,
    RefreshTokenRequest,
    TokenResponse,
    UserCreate,
    UserLogin,
    UserResponse,
    UserUpdate,
)
from app.services.user_service import UserService

# APIRouter is the FastAPI equivalent of Django's include-able URLconf.
# The prefix "/users" and tags=["Users"] are applied in main.py when mounting.
router = APIRouter()


# =============================================================================
# Public endpoints (no authentication required)
# =============================================================================

@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,   # 201 Created for resource creation
    summary="Register a new user",
    description=(
        "Create a new user account. "
        "Returns the created user profile (without password). "
        "Email must be unique."
    ),
)
def register(
    data: UserCreate,                      # ← Pydantic validates the request body
    db: Session = Depends(get_db),         # ← DB session injected per-request
):
    """
    User registration endpoint.

    FastAPI automatically:
      - Parses the JSON body into a UserCreate instance
      - Returns 422 if validation fails (wrong types, missing fields, etc.)
      - Returns 201 with the UserResponse on success

    Depends(get_db) injects a database session scoped to this request.
    The session is closed in the finally block of get_db() after this
    function returns — even if an exception is raised.

    DRF EQUIVALENT:
      class RegisterView(CreateAPIView):
          serializer_class = UserSerializer
          permission_classes = []  # AllowAny
    """
    user = UserService.register(db=db, data=data)
    return user


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Login and get JWT tokens",
    description=(
        "Authenticate with email and password. "
        "Returns access_token (short-lived) and refresh_token (long-lived). "
        "Include the access_token in subsequent requests: "
        "Authorization: Bearer <access_token>"
    ),
)
def login(
    data: UserLogin,
    db: Session = Depends(get_db),
):
    """
    Authentication endpoint — returns JWT access + refresh tokens.

    DRF EQUIVALENT: TokenObtainPairView from rest_framework_simplejwt.
    The difference: we accept JSON (not form data) and return a custom
    TokenResponse. simplejwt uses form data and returns {"access": ..., "refresh": ...}.
    """
    return UserService.authenticate(db=db, email=data.email, password=data.password)


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Refresh access token",
    description=(
        "Exchange a valid refresh token for a new access + refresh token pair. "
        "Refresh tokens are rotated on each use for enhanced security."
    ),
)
def refresh_token(
    data: RefreshTokenRequest,
    db: Session = Depends(get_db),
):
    """
    Token refresh endpoint — rotates both access and refresh tokens.

    DRF EQUIVALENT: TokenRefreshView from simplejwt.
    We rotate the refresh token on each use (not all implementations do this),
    which limits the window of opportunity if a refresh token is stolen.
    """
    return UserService.refresh_access_token(db=db, refresh_token=data.refresh_token)


# =============================================================================
# Protected endpoints (authentication required)
# =============================================================================

@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user profile",
)
def get_my_profile(
    # Depends(get_current_active_user):
    #   1. Extracts Bearer token from Authorization header
    #   2. Decodes JWT → email
    #   3. Fetches User from DB
    #   4. Checks user.is_active
    #   5. Returns the User ORM object — available as `current_user`
    #
    # DRF EQUIVALENT: self.request.user (set by JWTAuthentication backend)
    current_user: User = Depends(get_current_active_user),
):
    """
    Return the profile of the currently authenticated user.

    The `current_user` is already the full User ORM object resolved
    from the JWT — no additional DB call needed for a profile read.
    """
    return current_user


@router.patch(
    "/me",
    response_model=UserResponse,
    summary="Update current user profile",
    description="Partially update full_name and/or email. Only provided fields are updated.",
)
def update_my_profile(
    data: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Partial profile update.

    DRF EQUIVALENT:
      class ProfileView(UpdateAPIView):
          permission_classes = [IsAuthenticated]
          def partial_update(self, request, *args, **kwargs):
              ...
    """
    return UserService.update_profile(db=db, user=current_user, data=data)


@router.post(
    "/me/change-password",
    status_code=status.HTTP_200_OK,
    summary="Change password",
)
def change_password(
    data: PasswordChange,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Change the current user's password.

    Requires the current password for verification before accepting the new one.
    After changing the password, existing JWTs remain valid until expiry
    (to also invalidate them, implement a token blacklist or change the secret).
    """
    return UserService.change_password(db=db, user=current_user, data=data)


@router.delete(
    "/me",
    status_code=status.HTTP_200_OK,
    summary="Deactivate account",
    description="Soft-delete: marks the account as inactive. Data is retained.",
)
def deactivate_account(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Deactivate (soft-delete) the current user's account.

    DRF EQUIVALENT:
      class DeleteAccountView(DestroyAPIView):
          def perform_destroy(self, instance):
              instance.is_active = False
              instance.save()  # soft delete instead of instance.delete()
    """
    return UserService.deactivate_account(db=db, user=current_user)
