from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends

from app.core.models.note import NoteType
from app.core.schemas.taxonomy import NoteTaxonomy
from app.core.services.taxonomy_service import build_user_note_taxonomy
from app.dependencies import get_current_user

if TYPE_CHECKING:
    from app.core.schemas.auth import AuthUser


router = APIRouter()


@router.get("/taxonomy", response_model=NoteTaxonomy)
async def get_user_taxonomy(current_user: AuthUser = Depends(get_current_user)) -> NoteTaxonomy:
    """Return aggregated user taxonomy (e.g., unique normalized tags).

    Uses an admin client internally to avoid RLS issues while still scoping
    to the authenticated user's `user_id`.
    """
    taxonomy = await build_user_note_taxonomy(user_id=current_user.id)
    return taxonomy


@router.get("/note-types", response_model=list[str])
async def list_note_types() -> list[str]:
    """Return all supported note types for client-side filtering.

    Enum values are serialized to their string representation per Pydantic/JSON rules.
    """
    return [t.value for t in NoteType]


