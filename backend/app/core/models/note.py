from __future__ import annotations

from enum import Enum
from uuid import UUID, uuid4

from pydantic import Field, field_validator, model_validator

from .base import TimestampedModel


class NoteType(str, Enum):
    """Type of note for categorization."""

    NOTE = "note"
    TASK = "task"
    EVENT = "event"
    RECIPE = "recipe"
    VOCABULARY = "vocabulary"


class Note(TimestampedModel):
    """Note domain model."""

    id: UUID = Field(default_factory=uuid4, description="Unique note identifier")

    # Core content fields (at least one must be non-empty)
    title: str | None = Field(default=None, max_length=255, description="Note title")
    content: str | None = Field(default=None, max_length=10000, description="Note content")

    # Categorization and organization
    note_type: NoteType = Field(default=NoteType.NOTE, description="Type of note")
    tags: list[str] = Field(default_factory=list, description="Tags for categorization")

    # User and ownership
    user_id: UUID = Field(default_factory=uuid4, description="Owner of the note")

    # Organization
    is_archived: bool = Field(default=False, description="Whether note is archived")

    # pgvector embedding field - optimized for similarity search
    embedding: list[float] | None = Field(
        default=None,
        description="Vector embedding for semantic search (1536 dimensions for OpenAI)"
    )

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v: list[str]) -> list[str]:
        """Validate and normalize tags."""
        if not v:
            return v

        # Normalize tags: lowercase, remove duplicates, limit length
        normalized = []
        for tag in v:
            if tag and len(tag.strip()) > 0:
                normalized_tag = tag.strip().lower()[:50]  # Limit tag length
                if normalized_tag not in normalized:
                    normalized.append(normalized_tag)

        return normalized[:5]  # Limit to 5 tags

    @field_validator("embedding")
    @classmethod
    def validate_embedding(cls, v: list[float] | None) -> list[float] | None:
        """Validate embedding dimensions."""
        if v is not None and len(v) != 1536:  # OpenAI text-embedding-3-small dimensions
            raise ValueError("Embedding must be 1536-dimensional for OpenAI embeddings")
        return v

    @model_validator(mode="after")
    def validate_title_or_content(self) -> Note:
        """Ensure at least one of title or content is provided and non-empty.

        Also normalizes empty strings to None to keep storage consistent.
        """
        normalized_title = None
        if self.title is not None:
            stripped = self.title.strip()
            normalized_title = stripped if stripped else None

        normalized_content = None
        if self.content is not None:
            stripped = self.content.strip()
            normalized_content = stripped if stripped else None

        if not normalized_title and not normalized_content:
            raise ValueError("Either title or content must be provided and non-empty")

        self.title = normalized_title
        self.content = normalized_content
        return self

    # Prefer Pydantic v2 model_config for OpenAPI examples
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "id": str(uuid4()),
                    "title": "Dentist Appointment",
                    "content": "Dentist appointment on Monday at 10:00 AM. Don't forget to bring insurance card.",
                    "note_type": "event",
                    "tags": ["health", "appointment", "dentist"],
                    "user_id": str(uuid4()),
                }
            ]
        }
    }

