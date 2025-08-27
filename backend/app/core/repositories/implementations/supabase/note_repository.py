from __future__ import annotations

from datetime import datetime  # noqa: TCH003
from typing import TYPE_CHECKING, Any

from app.core.models.note import Note
from app.core.repositories.note_repository import NoteRepository
from app.core.schemas.note_search import NoteSearchResult
from app.utils.logging import get_logger

logger = get_logger(__name__)

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence
    from uuid import UUID

    from supabase import Client


class SupabaseNoteRepository(NoteRepository):
    """Supabase implementation of the NoteRepository.

    Uses Supabase's PostgREST client for CRUD. Assumes a `notes` table with columns
    matching the `Note` model fields. Vector similarity search is expected to be
    implemented via RPCs separately if needed.
    """

    TABLE_NAME = "notes"

    def __init__(self, client: Client) -> None:
        self._client: Client = client

    async def create(self, note: Note) -> Note:
        row = self._note_to_row(note)
        # Insert and return the created row
        resp = await self._run(
            lambda: self._client.table(self.TABLE_NAME)
            .insert(row)
            .execute()
        )
        data = self._first(resp.data)
        return self._row_to_note(data)

    async def get(self, note_id: UUID) -> Note | None:
        resp = await self._run(
            lambda: self._client.table(self.TABLE_NAME)
            .select("*")
            .eq("id", str(note_id))
            .limit(1)
            .execute()
        )
        items = resp.data or []
        if not items:
            return None
        return self._row_to_note(items[0])

    async def list(self, *, limit: int = 50, user_id: UUID | None = None) -> Sequence[Note]:
        def _query():
            q = self._client.table(self.TABLE_NAME).select("*")
            if user_id is not None:
                q = q.eq("user_id", str(user_id))
            return (
                q
                .order("created_at", desc=True)
                .limit(limit)
                .execute()
            )

        resp = await self._run(_query)
        items = resp.data or []
        return [self._row_to_note(i) for i in items]

    async def update_fields(self, note_id: UUID, changes: dict) -> Note | None:
        # Ensure we only send fields that belong to the row schema and avoid id/user_id mutation
        sanitized: dict[str, Any] = {k: v for k, v in (changes or {}).items() if k not in {"id", "user_id", "created_at", "updated_at"}}
        if not sanitized:
            # No-op; return current row if exists
            return await self.get(note_id)

        # Update and return the updated row
        resp = await self._run(
            lambda: self._client.table(self.TABLE_NAME)
            .update(sanitized)
            .eq("id", str(note_id))
            .execute()
        )
        items = resp.data or []
        if not items:
            return None
        return self._row_to_note(items[0])

    async def delete(self, note_id: UUID) -> bool:
        # Delete and check if anything was deleted
        resp = await self._run(
            lambda: self._client.table(self.TABLE_NAME)
            .delete()
            .eq("id", str(note_id))
            .execute()
        )
        items = resp.data or []
        return len(items) > 0

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
    ) -> Sequence[NoteSearchResult]:
        _ = user_id  # parameter kept for interface; RLS uses auth.uid()
        def _rpc():
            params: dict[str, Any] = {
                "p_query": query,
                "p_tags": tags,
                "p_match_all_tags": match_all_tags,
                "p_note_type": note_type,
                "p_is_archived": is_archived,
                "p_limit": limit,
            }
            return self._client.rpc("search_notes", params=params).execute()

        resp = await self._run(_rpc)
        rows: list[dict[str, Any]] = resp.data or []
        return [self._row_to_search_result(r) for r in rows]

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
    ) -> Sequence[NoteSearchResult]:
        _ = user_id  # parameter kept for interface; RLS uses auth.uid()
        def _rpc():
            params: dict[str, Any] = {
                "p_query": query,
                "p_query_embedding": query_embedding,
                "p_tags": tags,
                "p_match_all_tags": match_all_tags,
                "p_note_type": note_type,
                "p_is_archived": is_archived,
                "p_limit": limit,
                "p_alpha": alpha,
                "p_created_from": created_from.isoformat() if created_from else None,
                "p_created_to": created_to.isoformat() if created_to else None,
                "p_updated_from": updated_from.isoformat() if updated_from else None,
                "p_updated_to": updated_to.isoformat() if updated_to else None,
            }
            return self._client.rpc("search_notes_agent", params=params).execute()

        resp = await self._run(_rpc)
        rows: list[dict[str, Any]] = resp.data or []
        return [self._row_to_search_result(r) for r in rows]

    @staticmethod
    async def _run(func: Callable[[], Any]) -> Any:
        import asyncio
        return await asyncio.to_thread(func)

    @staticmethod
    def _first(data: Any) -> dict[str, Any]:
        if isinstance(data, list) and data:
            return data[0]
        if isinstance(data, dict):
            return data
        return {}

    @staticmethod
    def _parse_vector_string(vector_str: str | None) -> list[float] | None:
        """Parse vector string from pgvector into list[float].

        pgvector returns vectors as string representations like '[0.1,0.2,0.3]'
        that need to be parsed into Python lists for Pydantic validation.
        """
        if vector_str is None:
            return None

        try:
            cleaned = vector_str.strip("[]")
            if not cleaned:
                return None
            return [float(x.strip()) for x in cleaned.split(",")]
        except (ValueError, TypeError) as e:
            logger.warning(f"Failed to parse vector string '{vector_str}': {e}")
            return None

    @staticmethod
    def _row_to_note(row: dict[str, Any]) -> Note:
        # Normalize nullable columns for Pydantic constraints
        normalized = dict(row)

        # Filter out database-specific fields that aren't part of the Note model
        # This includes fields like 'lexeme' (full-text search) and 'rank' (search ranking)
        db_specific_fields = {"lexeme", "rank"}
        for field in db_specific_fields:
            normalized.pop(field, None)

        if "embedding" in normalized:
            normalized["embedding"] = SupabaseNoteRepository._parse_vector_string(normalized["embedding"])

        if normalized.get("tags") is None:
            normalized["tags"] = []
        return Note.model_validate(normalized)

    @staticmethod
    def _note_to_row(note: Note) -> dict[str, Any]:
        data = note.model_dump()
        # Ensure types are JSON-serializable for PostgREST
        data["id"] = str(note.id)
        data["user_id"] = str(note.user_id)

        # Convert datetime objects to ISO format strings for JSON serialization
        # This is required because Supabase's PostgREST client expects JSON-serializable data
        if data.get("created_at") is not None:
            data["created_at"] = data["created_at"].isoformat()
        if data.get("updated_at") is not None:
            data["updated_at"] = data["updated_at"].isoformat()

        if data.get("tags") is None:
            data["tags"] = []
        if data.get("embedding") is None:
            data.pop("embedding", None)

        return data

    @staticmethod
    def _row_to_search_result(row: dict[str, Any]) -> NoteSearchResult:
        normalized = dict(row)

        # Filter out database-specific fields that aren't part of the NoteSearchResult model
        # This includes fields like 'lexeme' (full-text search) but keeps 'rank' (search ranking)
        db_specific_fields = {"lexeme"}
        for field in db_specific_fields:
            normalized.pop(field, None)

        if "embedding" in normalized:
            normalized["embedding"] = SupabaseNoteRepository._parse_vector_string(normalized["embedding"])

        if normalized.get("tags") is None:
            normalized["tags"] = []

        return NoteSearchResult.model_validate(normalized)

