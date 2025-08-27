from __future__ import annotations

from uuid import UUID  # noqa: TCH003

from app.core.models.base import AppBaseModel


class AuthUser(AppBaseModel):
    """Authenticated user extracted from Supabase JWT."""

    id: UUID
    email: str
    role: str | None = None


