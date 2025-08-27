from __future__ import annotations

from pydantic import Field

from app.core.models.base import AppBaseModel


class ChatRequest(AppBaseModel):
    """User message for the notes assistant."""

    message: str = Field(..., min_length=1, description="User's message to the assistant")
    previous_response_id: str | None = Field(
        default=None,
        description=(
            "Optional previous response id to maintain conversation continuity across requests. "
            "Omit or set to null to start a fresh conversation (e.g., after page reload)."
        ),
    )
