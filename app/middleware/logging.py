# =============================================================================
# app/middleware/logging.py
#
# PURPOSE:
#   Custom HTTP middleware that logs every request and its response time.
#   This gives you production-grade observability — you can see slow endpoints,
#   error rates, and traffic patterns in your logs.
#
# ⭐ DRF EQUIVALENT / COMPARISON:
#
#   Django Middleware:
#   ─────────────────
#   Django middleware is a class-based system with specific hook methods:
#     - __init__(get_response):  called ONCE when the server starts
#     - __call__(request):       called for EVERY request
#     - process_request(request): before the view
#     - process_response(request, response): after the view
#
#   Example Django middleware:
#     class TimingMiddleware:
#         def __init__(self, get_response):
#             self.get_response = get_response  # next middleware / view
#
#         def __call__(self, request):
#             start = time.time()
#             response = self.get_response(request)  # ← runs entire stack
#             duration = time.time() - start
#             logger.info(f"{request.method} {request.path} {response.status_code} {duration:.3f}s")
#             return response
#
#   FastAPI Middleware:
#   ──────────────────
#   FastAPI uses Starlette's ASGI middleware. It wraps the entire app
#   and intercepts requests and responses using async code.
#
#   Key differences:
#     1. Django middleware is WSGI (synchronous); FastAPI is ASGI (async-capable)
#     2. In FastAPI you use `await call_next(request)` instead of `self.get_response(request)`
#     3. Both are middleware chains — they wrap each other like an onion
#     4. Django auto-discovers middleware from MIDDLEWARE list in settings.py;
#        FastAPI requires explicit `app.add_middleware(...)` in main.py
#
#   Registration:
#     Django:  settings.MIDDLEWARE = ['path.to.TimingMiddleware']
#     FastAPI: app.add_middleware(LoggingMiddleware)  [in main.py]
#
# HOW THE MIDDLEWARE CHAIN WORKS:
#
#   Incoming Request:
#   ─────────────────
#     Client → LoggingMiddleware → [other middleware] → Router → Route Handler
#
#   Outgoing Response:
#   ──────────────────
#     Route Handler → [other middleware] → LoggingMiddleware → Client
#
#   The await call_next(request) call is where control passes DOWN the chain.
#   Code before it = pre-processing (like Django's process_request)
#   Code after it  = post-processing (like Django's process_response)
# =============================================================================

import logging
import time
import uuid

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

# Configure the logger for this module
# In production, you'd configure structlog or loguru for JSON-structured logs
logger = logging.getLogger("api.access")


class LoggingMiddleware(BaseHTTPMiddleware):
    """
    ASGI middleware that logs every HTTP request with timing information.

    Inherits from BaseHTTPMiddleware (Starlette), which handles the ASGI
    protocol details. We only need to implement `dispatch()`.

    DRF EQUIVALENT:
      A Django middleware class with __init__() and __call__() methods,
      registered in settings.MIDDLEWARE. The logic is equivalent; the
      async/await syntax and ASGI protocol are the key differences.
    """

    def __init__(self, app: ASGIApp) -> None:
        """
        Called ONCE when the application starts.

        DRF EQUIVALENT: Django middleware's __init__(self, get_response)
        Both save a reference to the "next" handler in the middleware chain.
        """
        super().__init__(app)

    async def dispatch(self, request: Request, call_next) -> Response:
        """
        Called for EVERY incoming HTTP request.

        The `call_next(request)` call passes the request to the next
        middleware or eventually to the route handler.

        Flow:
          START TIMER
            ↓
          Log incoming request
            ↓
          await call_next(request)  ← runs the rest of the stack
            ↓
          Log response + elapsed time
            ↓
          Return response to client

        DRF EQUIVALENT:
          def __call__(self, request):
              start = time.time()
              response = self.get_response(request)  # ← synchronous equiv.
              elapsed = time.time() - start
              logger.info(...)
              return response
        """
        # ---------------------------------------------------------------
        # PRE-PROCESSING (before the route handler runs)
        # ---------------------------------------------------------------

        # Generate a unique ID for this request — useful for tracing a
        # single request through distributed logs
        request_id = str(uuid.uuid4())[:8]

        start_time = time.perf_counter()  # High-precision timer

        # Log the incoming request
        logger.info(
            f"[{request_id}] ▶ {request.method} {request.url.path}"
            + (f"?{request.url.query}" if request.url.query else "")
            + f" | Client: {request.client.host if request.client else 'unknown'}"
        )

        # ---------------------------------------------------------------
        # CALL THE REST OF THE MIDDLEWARE CHAIN / ROUTE HANDLER
        # ---------------------------------------------------------------
        try:
            response: Response = await call_next(request)
            process_time_ms = (time.perf_counter() - start_time) * 1000

            # ---------------------------------------------------------------
            # POST-PROCESSING (after the route handler returns)
            # ---------------------------------------------------------------

            # Add timing info to response headers (useful for debugging in browser DevTools)
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Process-Time-Ms"] = f"{process_time_ms:.2f}"

            # Choose log level based on status code
            # 2xx/3xx → INFO, 4xx → WARNING, 5xx → ERROR
            status_code = response.status_code
            if status_code >= 500:
                log_fn = logger.error
            elif status_code >= 400:
                log_fn = logger.warning
            else:
                log_fn = logger.info

            log_fn(
                f"[{request_id}] ◀ {request.method} {request.url.path}"
                f" | Status: {status_code}"
                f" | Time: {process_time_ms:.2f}ms"
            )

        except Exception as exc:
            # Log unhandled exceptions (FastAPI will still return a 500 response)
            process_time_ms = (time.perf_counter() - start_time) * 1000
            logger.error(
                f"[{request_id}] ✗ UNHANDLED EXCEPTION on"
                f" {request.method} {request.url.path}"
                f" | Error: {exc!r}"
                f" | Time: {process_time_ms:.2f}ms",
                exc_info=True,  # Include full traceback in log
            )
            raise  # Re-raise so FastAPI's exception handler returns a 500

        return response
