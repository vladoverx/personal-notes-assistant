from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel as PydanticBaseModel
from pydantic import ConfigDict, Field


class AppBaseModel(PydanticBaseModel):
    """Base model for all domain models."""

    model_config = ConfigDict(
        from_attributes=True,
        extra="forbid",
        populate_by_name=True,
    )


class TimestampedModel(AppBaseModel):
    """Base model with timestamp fields."""

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime | None = None
