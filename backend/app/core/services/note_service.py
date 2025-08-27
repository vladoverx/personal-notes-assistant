from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from app.core.models.note import Note, NoteType

if TYPE_CHECKING:
    from collections.abc import Sequence

    from app.core.repositories.note_repository import NoteRepository


class NoteService:
    """Service for managing notes with user-scoped access (RLS friendly)."""

    def __init__(self, repo: NoteRepository) -> None:
        self._repo = repo

    async def create_note(self, create_dto, user_id: UUID) -> Note:
        """Create a note for a specific user ensuring at least one field is set."""
        raw_title = create_dto.title if getattr(create_dto, "title", None) is not None else None
        raw_content = create_dto.content if getattr(create_dto, "content", None) is not None else None

        title = (raw_title or "").strip() if raw_title is not None else None
        content = (raw_content or "").strip() if raw_content is not None else None

        normalized_title = title if title else None
        normalized_content = content if content else None

        if not (normalized_title or normalized_content):
            raise ValueError("Either title or content must be provided and non-empty")

        note = Note(
            id=uuid4(),
            title=normalized_title,
            content=normalized_content,
            note_type=create_dto.note_type or NoteType.NOTE,
            tags=create_dto.tags or [],
            user_id=user_id,
            is_archived=bool(getattr(create_dto, "is_archived", False)),
        )
        return await self._repo.create(note)

    async def get_note(self, note_id: str | UUID, user_id: UUID) -> Note | None:
        """Return note if it exists and belongs to the user; otherwise None."""
        try:
            note_uuid = UUID(str(note_id))
        except ValueError:
            return None
        note = await self._repo.get(note_uuid)
        if note and note.user_id == user_id:
            return note
        return None

    async def list_notes(self, user_id: UUID, limit: int = 50) -> Sequence[Note]:
        """List notes for the given user, newest first."""
        return await self._repo.list(limit=limit, user_id=user_id)

    async def update_note(self, note_id: str | UUID, update_dto, user_id: UUID) -> Note | None:
        """Update a user's note with a partial changes dict.

        Ensures ownership and validates that at least one of title/content remains non-empty.
        """
        existing = await self.get_note(note_id, user_id)
        if not existing:
            return None


        raw_changes = update_dto.model_dump(exclude_unset=True)
        allowed_fields = {"title", "content", "note_type", "tags", "is_archived"}
        changes: dict = {}
        for key, value in raw_changes.items():
            if key not in allowed_fields:
                continue
            if isinstance(value, str):
                value = value.strip()
                if key in {"title", "content"} and value == "":
                    value = None
            changes[key] = value


        merged_title = changes.get("title", existing.title)
        merged_content = changes.get("content", existing.content)
        if not ((merged_title or "").strip() or (merged_content or "").strip()):
            raise ValueError("Either title or content must be provided and non-empty")

        return await self._repo.update_fields(UUID(str(note_id)), changes)

    async def delete_note(self, note_id: str | UUID, user_id: UUID) -> bool:
        """Delete a user's note if it exists and belongs to them."""
        note = await self.get_note(note_id, user_id)
        if not note:
            return False
        return await self._repo.delete(UUID(str(note_id)))


