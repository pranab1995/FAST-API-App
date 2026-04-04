# =============================================================================
# alembic/env.py
#
# PURPOSE:
#   Alembic environment script — runs when you execute any alembic command.
#   Connects Alembic to your SQLAlchemy models and database URL.
#
# DRF EQUIVALENT:
#   Django's migration framework auto-discovers models and generates migration
#   files per-app. Alembic requires this env.py to be configured, but in
#   exchange gives you:
#     - Single migration history across all models
#     - Transactional DDL (schema changes rolled back on failure in PG)
#     - Explicit downgrade scripts (Django has --fake, not real rollback)
#     - Fine-grained control over migration logic
#
# HOW AUTOGENERATE WORKS:
#   1. `alembic revision --autogenerate` runs this file
#   2. env.py imports Base.metadata (which has all your model schemas)
#   3. Alembic connects to the LIVE DATABASE and inspects its schema
#   4. It diffs metadata vs. live schema and generates a migration script
#   5. You review and apply: `alembic upgrade head`
# =============================================================================

import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# ---------------------------------------------------------------------------
# Make sure the project root is on the Python path so imports work
# ---------------------------------------------------------------------------
# When running alembic from the project root, Python may not have app/ on its
# path. This ensures `from app.xxx import yyy` works inside migration scripts.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# ---------------------------------------------------------------------------
# Import your app's Base metadata and settings
# ---------------------------------------------------------------------------
# This is the CRITICAL import for autogenerate — Base.metadata contains the
# schema of all models that imported from app/db/base.py.
# The imports in base.py (User, Task) populate Base.metadata.
from app.db.base import Base          # noqa: E402 — must be after sys.path
from app.core.config import settings  # noqa: E402

# ---------------------------------------------------------------------------
# Alembic config object (reads alembic.ini)
# ---------------------------------------------------------------------------
config = context.config

# Set up loggers from alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ---------------------------------------------------------------------------
# IMPORTANT: Inject the database URL from our Settings (not hardcoded in .ini)
# This means .env controls the DB URL — same as the running application.
# ---------------------------------------------------------------------------
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

# Tell Alembic which metadata to compare against (autogenerate target)
target_metadata = Base.metadata


# ---------------------------------------------------------------------------
# Migration modes
# ---------------------------------------------------------------------------

def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode (no live DB connection).

    Generates SQL script output that you can review and apply manually.
    Useful for production deployments where the migration server can't
    directly connect to the DB.

    DRF EQUIVALENT: python manage.py sqlmigrate (shows SQL without applying)
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    Run migrations in 'online' mode (live DB connection).

    Creates a connection, runs migrations inside a transaction, and commits.
    If a migration fails, the transaction is rolled back — no partial state.

    DRF EQUIVALENT: python manage.py migrate (applies migrations to live DB)
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,  # Don't pool connections during migrations
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # Compare server defaults (e.g., DEFAULT 'todo' on status column)
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
