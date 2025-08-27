from __future__ import annotations

from pydantic import Field

from app.core.models.base import AppBaseModel


class NoteEnrichmentResult(AppBaseModel):
    """Validated enrichment output for tags."""

    tags: list[str] = Field(
        description="List of tags for the note, maximum 5 tags",
        max_length=5,
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "tags": ["work", "meeting", "project"]
                }
            ]
        }
    }
