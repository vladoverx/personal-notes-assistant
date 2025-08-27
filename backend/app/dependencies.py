from __future__ import annotations

import math
import time
from typing import TYPE_CHECKING

from fastapi import Depends, HTTPException, Request, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import settings
from app.core.repositories.implementations.supabase.note_repository import (
    SupabaseNoteRepository,
)
from app.core.schemas.auth import AuthUser
from app.core.services.note_service import NoteService
from app.core.services.search_service import SearchService
from app.db.base import create_request_supabase_client
from app.utils.logging import get_logger
from app.utils.openai_client import get_openai_client

logger = get_logger(__name__)

# Use auto_error=False to handle missing tokens gracefully
http_bearer = HTTPBearer(auto_error=False)

if TYPE_CHECKING:
    from supabase import Client

    from app.core.repositories.note_repository import NoteRepository


# In-memory rate limiting
_login_attempts: dict[str, list[float]] = {}


def _is_rate_limited(identifier: str) -> bool:
    """Check if the identifier is rate limited."""
    if not settings.enable_rate_limiting:
        return False
    now = time.time()
    window_start = now - settings.login_attempt_window
    if identifier in _login_attempts:
        _login_attempts[identifier] = [
            attempt for attempt in _login_attempts[identifier]
            if attempt > window_start
        ]
    attempts = _login_attempts.get(identifier, [])
    if len(attempts) >= settings.max_login_attempts:
        return True
    if identifier not in _login_attempts:
        _login_attempts[identifier] = []
    _login_attempts[identifier].append(now)
    return False


async def _run_blocking(func):
    """Run blocking functions in a thread pool."""
    import asyncio
    return await asyncio.to_thread(func)


def rate_limit_by_ip(request: Request, operation: str = "default") -> None:
    """Rate limiting dependency that can be used in endpoints.

    Args:
        request: FastAPI request object
        operation: Operation identifier for rate limiting (e.g., "signin", "signup")

    Raises:
        HTTPException: If rate limit is exceeded
    """
    client_ip = request.client.host if request.client else "unknown"
    identifier = f"{operation}:{client_ip}"
    if _is_rate_limited(identifier):
        logger.warning(f"Rate limited {operation} attempt", extra={"ip": client_ip})

        now = time.time()
        window_seconds = settings.login_attempt_window
        limit = settings.max_login_attempts

        window_start = now - window_seconds
        attempts = _login_attempts.get(identifier, [])
        attempts = [ts for ts in attempts if ts > window_start]
        _login_attempts[identifier] = attempts

        earliest_attempt = min(attempts) if attempts else now
        seconds_until_reset = max(1, math.ceil(window_seconds - (now - earliest_attempt)))

        headers = {
            "Retry-After": str(seconds_until_reset),
            "RateLimit-Limit": str(limit),
            "RateLimit-Remaining": "0",
            "RateLimit-Reset": str(seconds_until_reset),
        }

        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many {operation} attempts. Please try again later.",
            headers=headers,
        )


def get_request_supabase_client(request: Request) -> Client:
    """Create a request-scoped Supabase client and set PostgREST bearer.

    Extracts the Authorization: Bearer <jwt> header if present and configures
    PostgREST to enforce RLS for the user.
    """
    auth_header = request.headers.get("authorization") or request.headers.get("Authorization")
    jwt: str | None = None
    if auth_header and auth_header.lower().startswith("bearer "):
        jwt = auth_header.split(" ", 1)[1].strip()
    return create_request_supabase_client(jwt)

def get_note_repository(client: Client = Depends(get_request_supabase_client)) -> NoteRepository:
    """Get a request-scoped note repository instance using request client."""
    return SupabaseNoteRepository(client)

def get_note_service(repo: NoteRepository = Depends(get_note_repository)) -> NoteService:
    """Get a request-scoped note service instance."""
    return NoteService(repo)

def get_search_service(repo: NoteRepository = Depends(get_note_repository)) -> SearchService:
    """Get a request-scoped search service instance."""
    return SearchService(repo)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Security(http_bearer),
) -> AuthUser:
    """Validate JWT via Supabase and return authenticated user."""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    jwt = credentials.credentials
    if not jwt or len(jwt.split(".")) != 3:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token format",
            headers={"WWW-Authenticate": "Bearer"},
        )
    supabase = create_request_supabase_client(jwt)
    try:
        resp = await _run_blocking(lambda: supabase.auth.get_user(jwt))
    except Exception as err:
        error_msg = str(err).lower()
        logger.warning(
            "JWT validation failed",
            extra={
                "error_type": type(err).__name__,
                "error_summary": error_msg[:100] if error_msg else "Unknown error",
                "jwt_length": len(jwt) if jwt else 0,
            }
        )
        if "invalid" in error_msg or "expired" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token is invalid or expired",
                headers={"WWW-Authenticate": "Bearer"},
            ) from err
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication failed",
                headers={"WWW-Authenticate": "Bearer"},
            ) from err
    user = getattr(resp, "user", None)
    if not user or not getattr(user, "id", None):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user data",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user_id = getattr(user, "id", None)
    email = getattr(user, "email", None)
    role = getattr(user, "role", None)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user ID",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return AuthUser(
        id=user_id,
        email=email or "",
        role=role,
    )


def get_auth_service(client: Client = Depends(get_request_supabase_client)):
    """Get a request-scoped auth service instance."""
    from app.core.services.auth_service import AuthService
    return AuthService(client)


def get_agent_service(
    note_service: NoteService = Depends(get_note_service),
    search_service: SearchService = Depends(get_search_service),
):
    """Construct AgentService with shared OpenAI client."""
    from app.core.services.agent_service import AgentService

    openai_client = get_openai_client()
    return AgentService(note_service, search_service, openai_client)
