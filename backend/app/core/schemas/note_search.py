from __future__ import annotations

from datetime import datetime  # noqa: TCH003
from uuid import UUID  # noqa: TCH003

from pydantic import Field

from app.core.models.base import AppBaseModel
from app.core.models.note import NoteType  # noqa: TCH001


class NoteSearchResult(AppBaseModel):
    """Typed result for search endpoints that include a ranking score."""

    id: UUID
    title: str | None
    content: str | None
    note_type: NoteType
    tags: list[str]
    user_id: UUID
    is_archived: bool
    created_at: datetime
    updated_at: datetime | None
    rank: float


class AgentSearchRequest(AppBaseModel):
    """Agent-only search request with extended filters and weighting.

    This is internal to the application layer (not exposed as a public API schema).
    """

    query: str | None = None
    tags: list[str] | None = None
    match_all_tags: bool = False
    note_type: NoteType | None = None
    is_archived: bool | None = None
    limit: int = Field(default=20, ge=1, le=200)

    created_from: datetime | None = None
    created_to: datetime | None = None
    updated_from: datetime | None = None
    updated_to: datetime | None = None

    alpha: float = Field(default=0.5, ge=0, le=1)

