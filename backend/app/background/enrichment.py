from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from app.core.services.enrichment_service import enrich_note_tags
from app.core.services.taxonomy_service import build_user_note_taxonomy
from app.db.base import get_supabase_admin_client
from app.utils.logging import get_logger

logger = get_logger(__name__)

if TYPE_CHECKING:
    from uuid import UUID


async def enrich_and_store_note_tags(
    *,
    note_id: UUID,
    user_id: UUID,
    title: str | None,
    content: str | None,
) -> None:
    """Background job to enrich tags and persist updates.

    Uses the Supabase admin client to bypass RLS in background tasks. Swallows
    errors and logs for observability.
    """
    logger.info("Starting enrichment job for note %s (user: %s)", note_id, user_id)
    logger.debug("Note details - title: %s, content length: %d",
                title, len(content) if content else 0)

    try:
        client = get_supabase_admin_client()

        def _get_current_note() -> Any:
            return (
                client
                .table("notes")
                .select("tags")
                .eq("id", str(note_id))
                .limit(1)
                .execute()
            )

        note_resp = await asyncio.to_thread(_get_current_note)
        logger.debug("Database response: %s", note_resp)

        current_row: dict[str, Any] = (note_resp.data or [{}])[0] or {}
        current_tags = current_row.get("tags") or []

        logger.debug("Current note data - tags: %s", current_tags)

        logger.info("Building user taxonomy for enrichment")
        taxonomy = await build_user_note_taxonomy(user_id=user_id, client=client)
        logger.debug("Taxonomy built - tag_vocab: %s",
                    taxonomy.tag_vocab if taxonomy else None)

        logger.info("Calling enrichment service")
        enriched = await enrich_note_tags(
            title=title,
            content=content,
            taxonomy=taxonomy,
            existing_tags=current_tags if isinstance(current_tags, list) else [],
        )
        logger.debug("Enrichment service returned: %s", enriched)

        if not enriched:
            logger.warning("No enrichment result received")
            return

        # Merge: prefer enriched tags but reuse existing union; ensure uniqueness, preserve order by favoring enriched suggestions first
        new_tags = [t.strip().lower() for t in (enriched.get("tags") or []) if isinstance(t, str) and t.strip()]

        merged_tags: list[str] = []
        for t in new_tags + [*(current_tags if isinstance(current_tags, list) else [])]:
            if isinstance(t, str):
                tt = t.strip().lower()
                if tt and tt not in merged_tags:
                    merged_tags.append(tt)

        logger.debug("Merged tags: %s", merged_tags)

        # No-op if nothing changed
        if merged_tags == (current_tags or []):
            logger.info("No changes detected, skipping database update")
            return

        payload = {
            "tags": merged_tags,
        }
        logger.info("Updating note with payload: %s", payload)

        await asyncio.to_thread(
            lambda: client
            .table("notes")
            .update(payload)
            .eq("id", str(note_id))
            .execute()
        )
        logger.info("Successfully updated note %s with enriched tags", note_id)

    except Exception as err:  # pragma: no cover - external failures
        logger.error("Enrichment job failed for note %s: %s", note_id, err)
        logger.error("Error type: %s", type(err).__name__)
        logger.error("Error details: %s", str(err))
        logger.error("Full error info: %s", err)


