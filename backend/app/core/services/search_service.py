from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence
    from uuid import UUID

    from app.api.v1.schemas.note_search import NoteSearchRequest
    from app.core.repositories.note_repository import NoteRepository
    from app.core.schemas.note_search import AgentSearchRequest, NoteSearchResult


class SearchService:
    """Service for searching notes.

    Keeps application logic (validation, defaults) outside transport layer.
    """

    def __init__(self, repo: NoteRepository) -> None:
        self._repo = repo

    async def search_notes(
        self,
        *,
        user_id: UUID,
        request: NoteSearchRequest,
    ) -> Sequence[NoteSearchResult]:
        return await self._repo.search_notes(
            user_id=user_id,
            query=request.query,
            tags=request.tags,
            match_all_tags=request.match_all_tags,
            note_type=(request.note_type.value if request.note_type else None),
            is_archived=request.is_archived,
            limit=request.limit,
        )

    async def search_notes_agent(
        self,
        *,
        user_id: UUID,
        request: AgentSearchRequest,
        query_embedding: list[float] | None,
    ) -> Sequence[NoteSearchResult]:
        return await self._repo.search_notes_agent(
            user_id=user_id,
            query=request.query,
            query_embedding=query_embedding,
            tags=request.tags,
            match_all_tags=request.match_all_tags,
            note_type=(request.note_type.value if request.note_type else None),
            is_archived=request.is_archived,
            limit=request.limit,
            alpha=request.alpha,
            created_from=request.created_from,
            created_to=request.created_to,
            updated_from=request.updated_from,
            updated_to=request.updated_to,
        )


