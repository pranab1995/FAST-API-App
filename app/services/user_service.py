# =============================================================================
# app/services/user_service.py
#
# PURPOSE:
#   The service layer contains ALL business logic for user operations.
#   It sits between the API router (HTTP layer) and the repository (DB layer).
#
# ⭐ DRF EQUIVALENT / KEY INSIGHT:
#   DRF has NO dedicated service layer by convention.
#   Business logic typically bleeds into views, serializers, or model methods:
#
#     DRF:
#       class RegisterView(CreateAPIView):
#           def perform_create(self, serializer):
#               if User.objects.filter(email=...).exists(): # ← business logic in view!
#                   raise ValidationError(...)
#               serializer.save(password=make_password(...))
#
#   FastAPI (our pattern):
#       Router  → validates input schema (Pydantic)
#       Service → checks if email exists, hashes password (THIS FILE)
#       Repo    → does db.add(user); db.commit()
#
#   Why this is better:
#     1. You can call user_service.register() from a CLI script, a
#        background task, or a test — no HTTP request needed.
#     2. The router is thin: no business logic leaks into the HTTP layer.
#     3. The repository is thin: no password hashing leaks into the DB layer.
#
# WHAT BELONGS IN A SERVICE:
#   ✅ "Does this email already exist?" checks
#   ✅ Password hashing before storage
#   ✅ Token creation after successful login
#   ✅ "Is the old password correct?" checks for password change
#   ✅ Orchestrating multiple repository calls in one transaction
#
# WHAT DOES NOT BELONG IN A SERVICE:
#   ❌ HTTP request/response objects (→ router)
#   ❌ Raw SQL queries (→ repository)
#   ❌ JWT decode logic (→ security.py)
# =============================================================================

from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.core.security import hash_password, verify_password, create_access_token, create_refresh_token
from app.models.user import User
from app.repositories.user_repo import UserRepository
from app.schemas.user import UserCreate, UserUpdate, PasswordChange, TokenResponse


class UserService:
    """
    Business logic layer for user-related operations.

    Instantiated per-request (or used as static methods) — no shared state.
    """

    @staticmethod
    def register(db: Session, data: UserCreate) -> User:
        """
        Register a new user.

        Business rules:
          1. Email must not already be registered → 409 Conflict
          2. Password is hashed before storage (plain text NEVER stored)
          3. Returns the created User ORM object

        Flow:
          Router → UserService.register() → UserRepository.create()
          ↓
          Validate email uniqueness → Hash password → Persist to DB

        DRF EQUIVALENT:
          UserSerializer.create() method, or overriding perform_create()
          in a CreateAPIView. In both cases, you'd call make_password()
          on the password field.
        """
        # Business rule: email must be unique
        existing_user = UserRepository.get_by_email(db, data.email)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Email '{data.email}' is already registered",
            )

        # Hash the plain password — NEVER pass raw password to the repo
        hashed = hash_password(data.password)

        # Persist via repository (no business logic there)
        user = UserRepository.create(
            db=db,
            email=data.email,
            full_name=data.full_name,
            hashed_password=hashed,
        )
        return user

    @staticmethod
    def authenticate(db: Session, email: str, password: str) -> TokenResponse:
        """
        Verify credentials and issue JWT tokens.

        Business rules:
          1. User must exist → 401 (vague error: don't reveal if email is registered)
          2. Password must match stored hash → 401
          3. Account must be active → 403
          4. Returns both access and refresh tokens on success

        SECURITY NOTE:
          We return the same "Invalid credentials" for both "user not found"
          and "wrong password" — this prevents user enumeration attacks
          (an attacker can't probe which emails are registered).

        DRF EQUIVALENT:
          TokenObtainPairView from simplejwt. The authentication backend
          (ModelBackend) handles the credential check; simplejwt wraps it.
        """
        # Step 1: Look up user (don't reveal if email exists or not)
        user = UserRepository.get_by_email(db, email)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Step 2: Verify password
        if not verify_password(password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Step 3: Check account is active
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is deactivated. Please contact support.",
            )

        # Step 4: Issue tokens
        # "sub" (subject) is a standard JWT claim = the user identifier
        token_data = {"sub": user.email}
        access_token = create_access_token(token_data)
        refresh_token = create_refresh_token(token_data)

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
        )

    @staticmethod
    def refresh_access_token(db: Session, refresh_token: str) -> TokenResponse:
        """
        Issue a new access token given a valid refresh token.

        Business rules:
          1. Refresh token must be valid (not expired, not tampered)
          2. Token type must be "refresh" (not "access")
          3. User must still exist and be active

        DRF EQUIVALENT: TokenRefreshView from simplejwt.
        """
        from app.core.security import decode_token

        payload = decode_token(refresh_token)
        if payload is None or payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired refresh token",
            )

        sub = payload.get("sub")
        if not sub or not isinstance(sub, str):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired refresh token",
            )
        
        user = UserRepository.get_by_email(db, sub)
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive",
            )

        token_data = {"sub": user.email}
        new_access_token = create_access_token(token_data)
        new_refresh_token = create_refresh_token(token_data)  # Rotate refresh token

        return TokenResponse(
            access_token=new_access_token,
            refresh_token=new_refresh_token,
        )

    @staticmethod
    def get_profile(db: Session, user_id: int) -> User:
        """
        Fetch a user's profile by ID.

        Raises 404 if the user does not exist (shouldn't happen for the
        current user, but included for completeness and other admin usages).
        """
        user = UserRepository.get_by_id(db, user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )
        return user

    @staticmethod
    def update_profile(db: Session, user: User, data: UserUpdate) -> User:
        """
        Update a user's profile fields.

        Business rules:
          1. If email is being changed, it must not be taken by another user
          2. Only non-None fields from the request are updated (partial update)

        DRF EQUIVALENT:
          partial=True serializer.save() in an UpdateAPIView, with
          validate_email() checking uniqueness.
        """
        update_data = data.model_dump(exclude_none=True)  # Skip None fields

        # Email uniqueness check (only if email is changing)
        if "email" in update_data and update_data["email"] != user.email:
            existing = UserRepository.get_by_email(db, update_data["email"])
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Email is already in use by another account",
                )

        return UserRepository.update(db, user, update_data)

    @staticmethod
    def change_password(db: Session, user: User, data: PasswordChange) -> dict:
        """
        Change a user's password after verifying the current one.

        Business rules:
          1. Current password must be correct → 400
          2. New password must differ from current → 400 (optional rule)
          3. New password is hashed before storage

        DRF EQUIVALENT:
          A custom APIView with a PasswordChangeSerializer where
          validate() checks the old password.
        """
        # Verify current password
        if not verify_password(data.current_password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect",
            )

        # Prevent setting the same password again
        if verify_password(data.new_password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="New password must be different from the current password",
            )

        hashed_new = hash_password(data.new_password)
        UserRepository.update(db, user, {"hashed_password": hashed_new})
        return {"message": "Password changed successfully"}

    @staticmethod
    def deactivate_account(db: Session, user: User) -> dict:
        """
        Soft-delete: mark account as inactive instead of deleting.

        Preserves all historical task data and audit logs.
        The user can no longer log in (authenticate() checks is_active).
        """
        UserRepository.update(db, user, {"is_active": False})
        return {"message": "Account deactivated successfully"}
