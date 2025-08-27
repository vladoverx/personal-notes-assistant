from __future__ import annotations

from pydantic import Field, model_validator

from app.core.models.base import AppBaseModel
from app.core.models.note import NoteType


class AgentNoteCreate(AppBaseModel):
    """Internal DTO for agent-driven note creation.

    Mirrors the tool parameter contract while enforcing minimal validation
    consistent with the domain services.
    """

    title: str | None = Field(default=None, max_length=500)
    content: str | None = Field(default=None, max_length=10000)
    note_type: NoteType = Field(default=NoteType.NOTE)
    # Optional fields not exposed to tools but required by services interface
    tags: list[str] | None = None
    is_archived: bool = False

    @model_validator(mode="after")
    def ensure_title_or_content(self) -> AgentNoteCreate:
        normalized_title = (self.title or "").strip() if self.title is not None else ""
        normalized_content = (self.content or "").strip() if self.content is not None else ""
        if not normalized_title and not normalized_content:
            raise ValueError("Either title or content must be provided and non-empty")
        self.title = normalized_title if normalized_title else None
        self.content = normalized_content if normalized_content else None
        return self


class AgentNoteUpdate(AppBaseModel):
    """Internal DTO for agent-driven note updates (partial)."""

    title: str | None = Field(default=None, max_length=500)
    content: str | None = Field(default=None, max_length=10000)
    note_type: NoteType | None = None
    is_archived: bool | None = None

    @model_validator(mode="after")
    def normalize_empties(self) -> AgentNoteUpdate:
        if self.title is not None and self.title.strip() == "":
            self.title = None
        if self.content is not None and self.content.strip() == "":
            self.content = None
        return self
