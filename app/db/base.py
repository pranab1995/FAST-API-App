# =============================================================================
# app/db/base.py
#
# PURPOSE:
#   Defines the SQLAlchemy DeclarativeBase that ALL models inherit from.
#   Also imports every model module so Alembic can discover them during
#   migration generation (autogenerate reads Base.metadata).
#
# DRF EQUIVALENT:
#   In Django, models.Model is the base class. Django's app registry
#   automatically discovers models inside each app's models.py.
#   Here we must explicitly import models — Alembic needs to see the
#   metadata populated before it can diff against the live database.
#
# WHY SEPARATE FROM session.py?
#   session.py = engine + session factory (connection concerns)
#   base.py    = metadata + model imports (schema concerns)
#   Keeping them separate avoids circular imports (models import Base,
#   base.py imports models — if engine creation was also here it would
#   get messy fast).
# =============================================================================

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """
    Base class for all SQLAlchemy ORM models.

    Every model in app/models/ will inherit from this class.
    SQLAlchemy tracks table schema through Base.metadata, which
    Alembic reads to generate migration scripts.
    """
    pass


# ---------------------------------------------------------------------------
# IMPORTANT: Import all models here so Alembic can discover them.
#
# When you run `alembic revision --autogenerate`, Alembic compares
# Base.metadata (in-memory schema) against the live DB schema.
# If a model is not imported here, Alembic won't know it exists
# and won't generate the CREATE TABLE statement for it.
#
# DRF EQUIVALENT:
#   Django discovers models automatically through INSTALLED_APPS.
#   Here we must be explicit — a small trade-off for no magic.
# ---------------------------------------------------------------------------

# These imports are not "unused" — they populate Base.metadata
from app.models.user import User        # noqa: F401
from app.models.task import Task        # noqa: F401
