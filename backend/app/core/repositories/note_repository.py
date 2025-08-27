from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime  # noqa: TCH003
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence
    from uuid import UUID

    from app.core.models.note import Note
    from app.core.schemas.note_search import NoteSearchResult


class NoteRepository(ABC):
    """Abstract repository interface for notes.

    Contract used by services and dependency injection. Implementations should
    perform I/O (database, network) and therefore expose async methods.
    """

    @abstractmethod
    async def create(self, note: Note) -> Note:  # pragma: no cover - interface only
        """Persist a new note and return the stored entity."""

    @abstractmethod
    async def get(self, note_id: UUID) -> Note | None:  # pragma: no cover
        """Fetch a note by id or return None if not found."""

    @abstractmethod
    async def list(self, *, limit: int = 50, user_id: UUID | None = None) -> Sequence[Note]:  # pragma: no cover
        """Return most recent notes, ordered by creation time descending.

        Args:
            limit: Maximum number of notes to return
            user_id: Optional user ID to filter notes by owner
        """

    @abstractmethod
    async def update_fields(self, note_id: UUID, changes: dict) -> Note | None:  # pragma: no cover
        """Partially update fields on a note and return the updated entity, or None if missing."""

    @abstractmethod
    async def delete(self, note_id: UUID) -> bool:  # pragma: no cover
        """Delete a note by id. Return True if a row was removed, False otherwise."""

    @abstractmethod
    async def search_notes(
        self,
        *,
        user_id: UUID,
        query: str | None,
        tags: list[str] | None,
        match_all_tags: bool,
        note_type: str | None,
        is_archived: bool | None,
        limit: int,
    ) -> Sequence[NoteSearchResult]: ...

    @abstractmethod
    async def search_notes_agent(
        self,
        *,
        user_id: UUID,
        query: str | None,
        query_embedding: list[float] | None,
        tags: list[str] | None,
        match_all_tags: bool,
        note_type: str | None,
        is_archived: bool | None,
        limit: int,
        alpha: float,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
        updated_from: datetime | None = None,
        updated_to: datetime | None = None,
    ) -> Sequence[NoteSearchResult]: ...
