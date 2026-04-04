# =============================================================================
# app/db/session.py
#
# PURPOSE:
#   Creates the SQLAlchemy engine and session factory.
#   The engine manages the connection pool; the session factory
#   creates individual sessions (one per request).
#
# DRF EQUIVALENT:
#   Django handles database connections transparently via its ORM backend
#   (defined in settings.DATABASES). There's no explicit engine or session
#   object in Django — it's all hidden behind the QuerySet API.
#
#   In FastAPI with SQLAlchemy, you:
#     1. Create the engine (like configuring the DB backend)
#     2. Create a SessionLocal factory (like Django's connection handler)
#     3. Use sessions explicitly in routes/services via Depends(get_db)
#
# CONNECTION POOLING:
#   SQLAlchemy uses a connection pool by default (QueuePool).
#   - pool_pre_ping=True: tests connections before use (handles stale
#     connections after DB restarts — similar to Django's CONN_MAX_AGE)
#   - pool_size and max_overflow can be tuned for production load
# =============================================================================

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

# ---------------------------------------------------------------------------
# Database engine
# ---------------------------------------------------------------------------

engine = create_engine(
    settings.DATABASE_URL,
    # Test the DB connection before handing it to the application.
    # Prevents "server closed the connection unexpectedly" errors after
    # the DB restarts or the connection goes stale.
    pool_pre_ping=True,

    # Echo SQL statements to stdout — useful for debugging.
    # Set to False in production (settings.DEBUG controls this).
    echo=settings.DEBUG,
)

# ---------------------------------------------------------------------------
# Session factory
# ---------------------------------------------------------------------------

# SessionLocal is a *factory* — calling SessionLocal() creates a new session.
# Each HTTP request gets its own session (via the get_db() dependency).
#
# autocommit=False: transactions must be committed explicitly (db.commit())
# autoflush=False:  changes are not flushed to DB until you call db.flush()
#                   or db.commit() — prevents partial writes
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)
