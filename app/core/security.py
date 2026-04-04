# =============================================================================
# app/core/security.py
#
# PURPOSE:
#   All cryptographic operations live here:
#     - Password hashing & verification (bcrypt via passlib)
#     - JWT access & refresh token creation (python-jose)
#     - JWT decoding & payload extraction
#
# DRF EQUIVALENT:
#   In Django REST Framework you'd typically use:
#     - django.contrib.auth.hashers for passwords
#     - djangorestframework-simplejwt for JWTs
#   Here we own the full implementation, which gives us complete control
#   (e.g., embedding custom claims, dual-token strategy, etc.)
#
# WHY SEPARATE FROM dependencies.py?
#   security.py = PURE functions (no FastAPI types, no DB access).
#   dependencies.py = FastAPI Depends() wrappers that USE security.py.
#   This separation makes security.py unit-testable without any HTTP context.
# =============================================================================

from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------

# CryptContext manages the hashing algorithm and handles automatic rehashing
# when a stronger algorithm is configured in the future.
# "bcrypt" is the industry-standard choice: it is slow by design, making
# brute-force attacks computationally expensive.
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain_password: str) -> str:
    """
    Hash a plain-text password using bcrypt.

    bcrypt automatically:
      - Generates a random salt per hash (no rainbow tables)
      - Encodes the salt INTO the hash string
      - Applies a configurable cost factor (work factor 12 by default)

    Returns a string like: $2b$12$<salt><hash>
    This string is safe to store directly in the DB.
    """
    return pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Compare a plain-text password against a stored bcrypt hash.

    passlib extracts the salt from the hash and re-hashes the plain password,
    then compares. This is constant-time comparison, preventing timing attacks.
    """
    return pwd_context.verify(plain_password, hashed_password)


# ---------------------------------------------------------------------------
# JWT token creation
# ---------------------------------------------------------------------------

def _create_token(data: Dict[str, Any], expires_delta: timedelta, token_type: str) -> str:
    """
    Internal helper: build and sign a JWT.

    JWT structure:
      Header:  {"alg": "HS256", "typ": "JWT"}
      Payload: {sub, exp, type, ...extra claims}
      Signature: HMAC-SHA256(base64(header) + "." + base64(payload), SECRET_KEY)

    Args:
        data:          Custom claims to embed (e.g., {"sub": "user@email.com"})
        expires_delta: How long until the token expires
        token_type:    "access" or "refresh" — stored as a claim so the
                       decode layer can reject wrong token types
    """
    payload = data.copy()
    expire = datetime.now(timezone.utc) + expires_delta

    payload.update({
        "exp": expire,          # Standard JWT expiration claim
        "iat": datetime.now(timezone.utc),  # Issued-at (useful for auditing)
        "type": token_type,     # Custom claim: prevents refresh tokens being
                                # used as access tokens and vice versa
    })

    encoded_jwt = jwt.encode(
        payload,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )
    return encoded_jwt


def create_access_token(data: Dict[str, Any]) -> str:
    """
    Create a short-lived access token (default: 30 minutes).

    Access tokens are sent with every API request in the Authorization header:
      Authorization: Bearer <access_token>

    Short lifespan limits damage if a token is intercepted.
    """
    return _create_token(
        data=data,
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        token_type="access",
    )


def create_refresh_token(data: Dict[str, Any]) -> str:
    """
    Create a long-lived refresh token (default: 7 days).

    Refresh tokens are used ONLY to obtain new access tokens.
    They should be stored securely (e.g., httpOnly cookie in production).
    They are NOT sent with every request — only to the /refresh endpoint.
    """
    return _create_token(
        data=data,
        expires_delta=timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        token_type="refresh",
    )


# ---------------------------------------------------------------------------
# JWT decoding
# ---------------------------------------------------------------------------

def decode_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Decode and validate a JWT.

    python-jose automatically checks:
      - Signature validity (prevents tampering)
      - Expiration (exp claim)
      - Algorithm match (prevents algorithm-switching attacks)

    Returns the payload dict on success, or None if the token is invalid.
    Callers (in dependencies.py) translate None → 401 HTTP response.
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
        return payload
    except JWTError:
        # JWTError covers: expired tokens, bad signatures, malformed tokens
        return None
