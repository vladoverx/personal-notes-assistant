from __future__ import annotations

from datetime import datetime  # noqa: TCH003
from uuid import UUID  # noqa: TCH003

from pydantic import Field, field_validator

from app.core.models.base import AppBaseModel
from app.core.models.note import NoteType  # noqa: TCH001


class NoteSearchRequest(AppBaseModel):
    query: str | None = Field(default=None, description="Keyword query")
    tags: list[str] | None = None
    match_all_tags: bool = False
    note_type: NoteType | None = None
    is_archived: bool | None = None
    limit: int = Field(default=20)

    @field_validator("limit")
    @classmethod
    def validate_limit(cls, v: int) -> int:
        return max(1, min(200, v))


class NoteSearchResultPublic(AppBaseModel):
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
