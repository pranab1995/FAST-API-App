# =============================================================================
# app/main.py
#
# PURPOSE:
#   Application entry point — creates the FastAPI app instance, registers
#   middleware, mounts routers, and configures global behaviour.
#
# ⭐ DRF EQUIVALENT:
#   This file is the combined equivalent of:
#
#     1. Django's manage.py        — application entry point, WSGI/ASGI server
#     2. Django's urls.py          — URL routing (router.include_router)
#     3. Django's settings.py      — partially (app config, CORS, etc.)
#     4. Django's apps.py          — app lifecycle (startup/shutdown events)
#     5. Django's wsgi.py/asgi.py  — the app object handed to the server
#
#   In Django these concerns are spread across many files maintained by the
#   framework's conventions. FastAPI is more explicit — you wire everything
#   together yourself here, which gives you full control.
#
# APPLICATION LIFECYCLE:
#   1. Python imports this module
#   2. FastAPI() instance is created
#   3. Middleware is registered (LIFO — last added, first to run)
#   4. Routers are mounted on URL prefixes
#   5. Uvicorn calls app as an ASGI callable for each connection
#
# PRODUCTION NOTE:
#   In production, run with:
#     uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
#   Or behind Gunicorn with Uvicorn workers:
#     gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker
# =============================================================================

import logging
import logging.config
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1 import user as user_router
from app.api.v1 import task as task_router
from app.core.config import settings
from app.middleware.logging import LoggingMiddleware

# ---------------------------------------------------------------------------
# Logging configuration
# ---------------------------------------------------------------------------
# Configure Python's standard logging system.
# In production, replace this with a JSON logging config (structlog / loguru)
# and ship logs to a centralized system (Loki, CloudWatch, Datadog, etc.)

LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "standard",
            "stream": "ext://sys.stdout",
        },
    },
    "loggers": {
        "api.access": {
            "handlers": ["console"],
            "level": "DEBUG" if settings.DEBUG else "INFO",
            "propagate": False,
        },
        "sqlalchemy.engine": {
            # Log SQL queries only in DEBUG mode
            "handlers": ["console"],
            "level": "INFO" if settings.DEBUG else "WARNING",
            "propagate": False,
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
}

logging.config.dictConfig(LOGGING_CONFIG)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Application lifespan (startup / shutdown events)
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application startup and shutdown logic.

    FastAPI's modern equivalent of @app.on_event("startup") and
    @app.on_event("shutdown") (now deprecated).

    Code BEFORE yield → runs at startup
    Code AFTER  yield → runs at shutdown

    DRF EQUIVALENT:
      Django's AppConfig.ready() method for startup logic.
      There's no built-in shutdown hook in Django.

    Usage examples:
      Startup:  verify DB connection, warm up caches, start background tasks
      Shutdown: flush buffers, close external connections, drain queues
    """
    # Startup
    logger.info(f"🚀 Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    logger.info(f"   Debug mode: {settings.DEBUG}")
    logger.info(f"   Database:   {settings.DATABASE_URL.split('@')[-1]}")  # Hide credentials

    yield  # ← Application runs here

    # Shutdown
    logger.info(f"🛑 Shutting down {settings.APP_NAME}")


# ---------------------------------------------------------------------------
# FastAPI application instance
# ---------------------------------------------------------------------------

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="""
    ## Task Management API

    A production-style backend demonstrating:

    - **JWT Authentication** (access + refresh tokens)
    - **CRUD operations** with proper layered architecture
    - **User-specific data isolation** (users see only their tasks)
    - **Pagination & filtering** on list endpoints
    - **Repository → Service → Router** design pattern

    ### Authentication
    1. Register: `POST /api/v1/users/register`
    2. Login: `POST /api/v1/users/login` → get tokens
    3. Use: `Authorization: Bearer <access_token>` on protected routes
    4. Refresh: `POST /api/v1/users/refresh` when access token expires
    """,
    docs_url="/docs",          # Swagger UI at /docs
    redoc_url="/redoc",        # ReDoc at /redoc
    openapi_url="/openapi.json",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Middleware registration
# ---------------------------------------------------------------------------
# IMPORTANT: Middleware is executed in REVERSE registration order.
# The LAST middleware added is the OUTERMOST (first to handle a request).
#
# Order below → execution order for a request:
#   LoggingMiddleware (outermost) → CORSMiddleware → Route Handler
#
# DRF EQUIVALENT:
#   settings.MIDDLEWARE = [
#       'app.middleware.logging.LoggingMiddleware',
#       'corsheaders.middleware.CorsMiddleware',
#       ...
#   ]

# 1. Custom request/response logging
app.add_middleware(LoggingMiddleware)

# 2. CORS — configure allowed origins for your frontend domain
# In production: replace "*" with your actual frontend domain(s)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.DEBUG else ["https://yourdomain.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Router mounting
# ---------------------------------------------------------------------------
# Each router handles a URL prefix and a group of related endpoints.
# This is the FastAPI equivalent of Django's URL patterns with include().
#
# DRF EQUIVALENT:
#   urlpatterns = [
#       path('api/v1/users/', include('users.urls')),
#       path('api/v1/tasks/', include('tasks.urls')),
#   ]
#
# tags= controls grouping in Swagger UI (auto-generated interactive docs)

app.include_router(
    user_router.router,
    prefix="/api/v1/users",
    tags=["Users"],
)

app.include_router(
    task_router.router,
    prefix="/api/v1/tasks",
    tags=["Tasks"],
)


# ---------------------------------------------------------------------------
# Root health check endpoint
# ---------------------------------------------------------------------------

@app.get("/", tags=["Health"], summary="Health check")
async def root():
    """
    Root endpoint — confirms the API is alive.

    DRF EQUIVALENT: A simple APIView returning Response({"status": "ok"}).
    Used by load balancers and monitoring tools to verify the service is up.
    """
    return {
        "status": "healthy",
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
    }


@app.get("/health", tags=["Health"], summary="Detailed health check")
async def health_check():
    """
    Detailed health check including configuration info.

    In production, extend this to ping the database and return
    DB connection status, memory usage, etc.
    """
    return JSONResponse(
        content={
            "status": "healthy",
            "service": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "debug": settings.DEBUG,
        }
    )
