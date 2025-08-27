from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from app.core.services.embedding_service import build_note_text, create_embedding
from app.db.base import get_supabase_admin_client
from app.utils.logging import get_logger

logger = get_logger(__name__)

if TYPE_CHECKING:
    from uuid import UUID


async def generate_and_store_note_embedding(*, note_id: UUID, title: str | None, content: str | None) -> None:
    """Generate embedding for a note and persist it to Supabase as background work.

    Uses the admin client to bypass RLS for background updates. No-ops on errors.
    """
    try:
        text = build_note_text(title, content)
        if not text.strip():
            logger.warning("No text content to embed for note %s", note_id)
            return

        vector = await create_embedding(text)
        if not vector:
            logger.warning("Failed to generate embedding for note %s", note_id)
            return

        client = get_supabase_admin_client()

        await asyncio.to_thread(
            lambda: client
            .table("notes")
            .update({"embedding": vector})
            .eq("id", str(note_id))
            .execute()
        )
    except Exception as err:  # pragma: no cover - network/db errors
        logger.error("Embedding job failed for note %s: %s", note_id, err)


