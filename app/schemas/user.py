# =============================================================================
# app/schemas/user.py
#
# PURPOSE:
#   Pydantic schemas that define the "shape" of data coming IN (requests)
#   and going OUT (responses) for user-related endpoints.
#
# ⭐ DRF EQUIVALENT:
#   Pydantic schemas = DRF Serializers
#
#   DRF Serializer does:
#     - Validate incoming data (request body) ✓
#     - Serialize outgoing data (response body) ✓
#     - Field-level and object-level validation ✓
#
#   Pydantic schemas do the SAME — but with a cleaner, type-hint-based API
#   and no need for Meta classes or explicit field declarations for simple types.
#
# KEY DESIGN PATTERN — Request vs Response schemas:
#   We NEVER reuse the same schema for both input and output.
#   Why? Because the data you accept (plain password) is different from
#   the data you return (no password at all). Mixing them would be a
#   security risk and a design smell.
#
#   UserCreate  → request body for POST /users/register
#   UserLogin   → request body for POST /users/login
#   UserResponse→ response body (NEVER includes password)
#   UserUpdate  → request body for PATCH /users/me
#
# VALIDATION:
#   Pydantic validates at the boundary — when FastAPI parses the request.
#   If validation fails, FastAPI returns a 422 Unprocessable Entity with
#   a detailed error list, automatically — no try/except needed.
# =============================================================================

import re
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator


# ---------------------------------------------------------------------------
# Request schemas (data coming IN from the client)
# ---------------------------------------------------------------------------

class UserCreate(BaseModel):
    """
    Schema for user registration.

    DRF EQUIVALENT: UserSerializer with write_only=True on password field.

    The plain password is accepted here and immediately hashed in the service
    layer — it is NEVER stored or returned as plain text.
    """
    full_name: str = Field(
        ...,
        min_length=2,
        max_length=100,
        description="User's display name",
        examples=["Alice Johnson"],
    )
    email: EmailStr = Field(
        ...,
        description="Unique email address used for login",
        examples=["alice@example.com"],
    )
    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="Plain-text password (hashed before storage)",
        examples=["SecurePass123!"],
    )

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        """
        Enforce basic password strength rules.

        In DRF you'd use a custom validate_password() method or
        Django's validate_password() with AUTH_PASSWORD_VALIDATORS.
        """
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"[0-9]", v):
            raise ValueError("Password must contain at least one digit")
        return v

    @field_validator("full_name")
    @classmethod
    def full_name_no_numbers(cls, v: str) -> str:
        """Names shouldn't contain digits."""
        if any(char.isdigit() for char in v):
            raise ValueError("Full name must not contain numbers")
        return v.strip()


class UserLogin(BaseModel):
    """
    Schema for user login credentials.

    NOTE: We don't use OAuth2PasswordRequestForm here because that requires
    form-encoded data (application/x-www-form-urlencoded). We prefer JSON
    for a modern API. The OAuth2PasswordBearer scheme is still used for
    token verification on protected routes.
    """
    email: EmailStr = Field(..., examples=["alice@example.com"])
    password: str = Field(..., examples=["SecurePass123!"])


class UserUpdate(BaseModel):
    """
    Schema for partial user profile updates (PATCH).

    All fields are Optional — the client only sends what they want to change.

    DRF EQUIVALENT: partial=True on a serializer, or a dedicated UpdateSerializer.
    """
    full_name: Optional[str] = Field(None, min_length=2, max_length=100)
    email: Optional[EmailStr] = None


class PasswordChange(BaseModel):
    """
    Schema for password change requests.

    Requires the current password to prevent unauthorized changes
    (e.g., if someone hijacks a session).
    """
    current_password: str = Field(..., min_length=8)
    new_password: str = Field(..., min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"[0-9]", v):
            raise ValueError("Password must contain at least one digit")
        return v


# ---------------------------------------------------------------------------
# Response schemas (data going OUT to the client)
# ---------------------------------------------------------------------------

class UserResponse(BaseModel):
    """
    Schema for user data returned in API responses.

    CRITICAL: hashed_password is deliberately EXCLUDED.
    No matter what the DB returns, Pydantic will only serialize
    the fields declared here.

    DRF EQUIVALENT:
      class UserSerializer(serializers.ModelSerializer):
          class Meta:
              model = User
              fields = ['id', 'email', 'full_name', 'is_active', 'created_at']
              # Note: password NOT in fields
    """
    id: int
    email: EmailStr
    full_name: str
    is_active: bool
    created_at: datetime

    class Config:
        # from_orm=True / model_validate(): allows Pydantic to read data
        # from SQLAlchemy model instances (not just dicts)
        # DRF EQUIVALENT: This is what DRF does automatically when you pass
        # a Django model instance to a serializer.
        from_attributes = True  # Pydantic v2 equivalent of orm_mode = True


# ---------------------------------------------------------------------------
# Token schemas
# ---------------------------------------------------------------------------

class TokenResponse(BaseModel):
    """
    Response schema for login / token refresh endpoints.

    DRF EQUIVALENT: The response dict from simplejwt's TokenObtainPairView:
      {"access": "...", "refresh": "..."}
    """
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshTokenRequest(BaseModel):
    """Request body for the token refresh endpoint."""
    refresh_token: str
