from __future__ import annotations

from datetime import datetime  # noqa: TCH003
from uuid import UUID  # noqa: TCH003

from pydantic import Field, field_validator, model_validator

from app.core.models.base import AppBaseModel
from app.core.models.note import NoteType  # noqa: TCH001


class NoteCreate(AppBaseModel):
    title: str | None = Field(default=None, max_length=255, description="Note title")
    content: str | None = Field(default=None, max_length=10000, description="Note content")
    note_type: NoteType = Field(default=NoteType.NOTE, description="Type of note")
    tags: list[str] = Field(default_factory=list, description="Tags for categorization")
    is_archived: bool = Field(default=False, description="Whether note is archived")

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v: list[str]) -> list[str]:
        if not v:
            return v
        normalized: list[str] = []
        for tag in v:
            if tag and len(tag.strip()) > 0:
                normalized_tag = tag.strip().lower()[:50]
                if normalized_tag not in normalized:
                    normalized.append(normalized_tag)
        return normalized[:5]

    @model_validator(mode="after")
    def validate_title_or_content(self) -> NoteCreate:
        title = (self.title or "").strip() if self.title is not None else ""
        content = (self.content or "").strip() if self.content is not None else ""
        if not title and not content:
            raise ValueError("Either title or content must be provided and non-empty")
        # Normalize empty strings to None
        self.title = title if title else None
        self.content = content if content else None
        return self


class NoteUpdate(AppBaseModel):
    title: str | None = Field(default=None, max_length=255)
    content: str | None = Field(default=None, max_length=10000)
    note_type: NoteType | None = None
    tags: list[str] | None = None
    is_archived: bool | None = None

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return v
        normalized: list[str] = []
        for tag in v:
            if tag and len(tag.strip()) > 0:
                normalized_tag = tag.strip().lower()[:50]
                if normalized_tag not in normalized:
                    normalized.append(normalized_tag)
        return normalized[:5]

    @model_validator(mode="after")
    def normalize_optional_strings(self) -> NoteUpdate:
        # Convert empty strings to None for partial updates
        if self.title is not None and self.title.strip() == "":
            self.title = None
        if self.content is not None and self.content.strip() == "":
            self.content = None
        return self


class NoteRead(AppBaseModel):
    id: UUID
    title: str | None
    content: str | None
    note_type: NoteType
    tags: list[str]
    user_id: UUID
    is_archived: bool
    created_at: datetime
    updated_at: datetime | None


