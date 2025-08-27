from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID  # noqa: TCH003

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status

from app.api.v1.schemas.note import NoteCreate, NoteRead, NoteUpdate
from app.api.v1.schemas.note_search import NoteSearchRequest, NoteSearchResultPublic
from app.background import enrich_and_store_note_tags, generate_and_store_note_embedding
from app.dependencies import (
    get_current_user,
    get_note_service,
    get_search_service,
)

if TYPE_CHECKING:
    from app.core.schemas.auth import AuthUser
    from app.core.services.note_service import NoteService
    from app.core.services.search_service import SearchService

router = APIRouter()


@router.post("/", response_model=NoteRead, status_code=status.HTTP_201_CREATED)
async def create_note(
    payload: NoteCreate,
    background_tasks: BackgroundTasks,
    current_user: AuthUser = Depends(get_current_user),
    service: NoteService = Depends(get_note_service),
):
    note = await service.create_note(payload, user_id=current_user.id)
    background_tasks.add_task(
        generate_and_store_note_embedding,
        note_id=note.id,
        title=note.title,
        content=note.content,
    )
    background_tasks.add_task(
        enrich_and_store_note_tags,
        note_id=note.id,
        user_id=current_user.id,
        title=note.title,
        content=note.content,
    )
    return NoteRead.model_validate(note)


@router.get("/", response_model=list[NoteRead])
async def list_notes(
    limit: int = 50,
    current_user: AuthUser = Depends(get_current_user),
    service: NoteService = Depends(get_note_service),
):
    notes = await service.list_notes(user_id=current_user.id, limit=limit)
    return [NoteRead.model_validate(n) for n in notes]


@router.get("/{note_id}", response_model=NoteRead)
async def get_note(
    note_id: UUID,
    current_user: AuthUser = Depends(get_current_user),
    service: NoteService = Depends(get_note_service),
):
    note = await service.get_note(note_id, user_id=current_user.id)
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    return NoteRead.model_validate(note)


@router.patch("/{note_id}", response_model=NoteRead)
async def update_note(
    note_id: UUID,
    payload: NoteUpdate,
    background_tasks: BackgroundTasks,
    current_user: AuthUser = Depends(get_current_user),
    service: NoteService = Depends(get_note_service),
):
    note = await service.update_note(note_id, payload, user_id=current_user.id)
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    background_tasks.add_task(
        generate_and_store_note_embedding,
        note_id=note.id,
        title=note.title,
        content=note.content,
    )
    background_tasks.add_task(
        enrich_and_store_note_tags,
        note_id=note.id,
        user_id=current_user.id,
        title=note.title,
        content=note.content,
    )
    return NoteRead.model_validate(note)


@router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_note(
    note_id: UUID,
    current_user: AuthUser = Depends(get_current_user),
    service: NoteService = Depends(get_note_service),
):
    deleted = await service.delete_note(note_id, user_id=current_user.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Note not found")
    return None


@router.post("/search", response_model=list[NoteSearchResultPublic])
async def search_notes(
    payload: NoteSearchRequest,
    current_user: AuthUser = Depends(get_current_user),
    service: SearchService = Depends(get_search_service),
):
    """Search notes for the authenticated user.

    Uses lexical search (and server-side ranking) suitable for UI queries.
    """
    results = await service.search_notes(user_id=current_user.id, request=payload)
    # Coerce to public schema; UUID fields are preserved and serialized as strings in JSON
    return [NoteSearchResultPublic.model_validate(r) for r in results]


