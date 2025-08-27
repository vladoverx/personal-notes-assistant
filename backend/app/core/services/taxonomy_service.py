from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from app.core.schemas.taxonomy import NoteTaxonomy
from app.db.base import get_supabase_admin_client
from app.utils.logging import get_logger

if TYPE_CHECKING:
    from uuid import UUID

    from supabase import Client


logger = get_logger(__name__)


async def build_user_note_taxonomy(*, user_id: UUID, client: Client | None = None) -> NoteTaxonomy:
    """Aggregate unique tags for a user's notes.

    Uses the admin client to ensure background jobs are not blocked by RLS. Results
    are normalized to lowercase for tags.
    """
    supabase: Client = client or get_supabase_admin_client()

    page_size = 1000
    offset = 0
    tag_set: set[str] = set()

    while True:
        def _fetch_page(start: int, size: int) -> Any:
            return (
                supabase
                .table("notes")
                .select("tags")
                .eq("user_id", str(user_id))
                .range(start, start + size - 1)
                .execute()
            )

        try:
            resp = await asyncio.to_thread(_fetch_page, offset, page_size)
        except Exception as err:  # pragma: no cover - network/db errors
            logger.error("Failed to build taxonomy for user %s: %s", user_id, err)
            break

        rows: list[dict[str, Any]] = resp.data or []
        if not rows:
            break

        for row in rows:
            tags = row.get("tags") or []
            if isinstance(tags, list):
                for t in tags:
                    if isinstance(t, str):
                        tag_set.add(t.strip().lower())

        if len(rows) < page_size:
            break
        offset += page_size

    return NoteTaxonomy(tag_vocab=sorted(tag_set))


