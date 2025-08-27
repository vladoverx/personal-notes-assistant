from __future__ import annotations

from typing import TYPE_CHECKING

from starlette.middleware.base import BaseHTTPMiddleware

from app.utils.logging import get_logger

if TYPE_CHECKING:
    from fastapi import Request
    from starlette.types import ASGIApp

logger = get_logger(__name__)


class SecurityMiddleware(BaseHTTPMiddleware):
    """Security middleware to add essential security headers."""

    def __init__(self, app: ASGIApp):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Allow connections to our API host and Supabase
        csp_policy = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "img-src 'self' data: https:; "
            "font-src 'self' data: https://fonts.gstatic.com; "
            "connect-src 'self' https://api.notekin.online https://*.supabase.co; "
            "frame-ancestors 'none';"
        )
        response.headers["Content-Security-Policy"] = csp_policy

        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = "max-age=15552000; includeSubDomains"

        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"

        if request.url.path.startswith("/api/v1/auth"):
            client_ip = request.client.host if request.client else "unknown"
            user_agent = request.headers.get("user-agent", "unknown")

            logger.info(
                "Auth endpoint accessed",
                extra={
                    "path": request.url.path,
                    "method": request.method,
                    "ip": client_ip,
                    "user_agent": user_agent[:100],
                }
            )

        return response
