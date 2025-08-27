from __future__ import annotations

from pydantic import Field

from app.core.models.base import AppBaseModel


class NoteTaxonomy(AppBaseModel):
    """Aggregated vocabulary for notes within a user's workspace.

    - tag_vocab: unique, normalized tags observed across the user's notes
    """

    tag_vocab: list[str] = Field(default_factory=list)


