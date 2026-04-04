# =============================================================================
# app/core/dependencies.py
#
# PURPOSE:
#   FastAPI dependency functions injected via Depends().
#   Think of this as the "plumbing" that wires together:
#     - Database sessions (one per request, closed after response)
#     - Authenticated user resolution (reads JWT → fetches User from DB)
#
# ⭐ DRF EQUIVALENT / KEY CONCEPT:
#   In Django REST Framework:
#     - The DB session is managed automatically (Django ORM connection pooling)
#     - The authenticated user is set on request.user via authentication classes
#       (e.g., JWTAuthentication from simplejwt)
#     - You access it as `self.request.user` inside a ViewSet
#
#   In FastAPI:
#     - There is NO magical `request.user`. You must EXPLICITLY declare
#       your dependencies. This is verbose but makes data flow crystal clear.
#     - Example: `current_user: User = Depends(get_current_user)`
#       — this one line tells you EXACTLY where the user comes from.
#
# WHY DEPENDENCY INJECTION IS POWERFUL:
#   - Testability: in tests, override Depends() with mock functions
#   - Reusability: get_current_user is used in dozens of routes with one line
#   - Layered deps: get_current_active_user wraps get_current_user,
#     adding the "is_active" check cleanly without repeating code
# =============================================================================

from typing import Generator

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.security import decode_token
from app.db.session import SessionLocal
from app.models.user import User

# ---------------------------------------------------------------------------
# OAuth2 scheme
# ---------------------------------------------------------------------------

# OAuth2PasswordBearer tells FastAPI:
#   1. Where clients send tokens (the tokenUrl endpoint)
#   2. That the Authorization: Bearer <token> header is expected
#
# FastAPI uses this to auto-generate the "Authorize" button in Swagger UI.
# DRF EQUIVALENT: TokenAuthentication or JWTAuthentication class definition.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/users/login")


# ---------------------------------------------------------------------------
# Database session dependency
# ---------------------------------------------------------------------------

def get_db() -> Generator:
    """
    Yield a SQLAlchemy session for the duration of one HTTP request.

    This is a generator dependency — FastAPI calls next() before the route
    handler runs (providing the session), then resumes after the handler
    returns (triggering the finally block).

    Flow:
      1. Request comes in → FastAPI calls get_db()
      2. SessionLocal() creates a DB connection
      3. session is yielded into the route handler
      4. Route handler runs, using the session
      5. Response is returned to client
      6. FastAPI resumes get_db() after yield → finally block runs
      7. session.close() returns the connection to the pool

    DRF EQUIVALENT:
      Django manages DB connections transparently per-request via middleware
      (django.db.backends.base.DatabaseWrapper). There's no explicit session
      object in DRF views — you just call MyModel.objects.filter(...).
      FastAPI requires you to pass the session explicitly, which is more
      verbose but also more predictable and testable.

    WHY yield AND NOT return?
      Using yield (a context manager pattern) guarantees cleanup even if
      an exception is raised inside the route handler. The finally block
      ALWAYS runs, preventing connection leaks.
    """
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Authentication dependencies
# ---------------------------------------------------------------------------

def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    Resolve the JWT token → User object.

    This dependency is the heart of FastAPI authentication.
    It:
      1. Extracts the Bearer token from the Authorization header
         (handled by oauth2_scheme)
      2. Decodes and validates the JWT (handled by decode_token)
      3. Extracts the user identifier from the "sub" claim
      4. Fetches the full User record from the database
      5. Returns the User — or raises 401 if any step fails

    DRF EQUIVALENT:
      JWTAuthentication.authenticate(request) in djangorestframework-simplejwt
      which sets request.user and request.auth. In FastAPI, instead of
      accessing request.user anywhere, you declare this dependency explicitly:

        @router.get("/profile")
        def get_profile(current_user: User = Depends(get_current_user)):
            ...

      This explicit declaration makes permissions visible in the function
      signature itself — no need to read class-level permission_classes.

    RAISES:
      HTTP 401 if:
        - Token is missing (handled by oauth2_scheme itself)
        - Token signature is invalid or expired (decode_token returns None)
        - "sub" claim is missing (malformed token)
        - "type" claim is not "access" (refresh token used as access token)
        - User not found in DB (deleted after token was issued)
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},  # RFC 6750 compliance
    )

    payload = decode_token(token)
    if payload is None:
        raise credentials_exception

    # Ensure this is an access token, not a refresh token
    if payload.get("type") != "access":
        raise credentials_exception

    email: str = payload.get("sub")
    if email is None:
        raise credentials_exception

    # Fetch the user from DB — confirms the user still exists
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        raise credentials_exception

    return user


def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Extend get_current_user with an active-status check.

    If an admin deactivates a user account, their existing valid JWTs
    would still pass get_current_user (token is not expired). This layer
    catches that case.

    DRF EQUIVALENT:
      In DRF you'd add IsActive to permission_classes, e.g.:
        permission_classes = [IsAuthenticated, IsActive]
      Here we stack Depends() instead — same concept, explicit declaration.

    Usage in routes:
        current_user: User = Depends(get_current_active_user)
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user account",
        )
    return current_user
