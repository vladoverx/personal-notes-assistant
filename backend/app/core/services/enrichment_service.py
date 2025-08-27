from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.config import settings
from app.core.schemas.enrichment import NoteEnrichmentResult
from app.core.services.embedding_service import build_note_text
from app.utils.logging import get_logger
from app.utils.openai_client import get_openai_client

if TYPE_CHECKING:
    from app.core.schemas.taxonomy import NoteTaxonomy

logger = get_logger(__name__)


async def enrich_note_tags(
    *,
    title: str | None,
    content: str | None,
    taxonomy: NoteTaxonomy | None = None,
    existing_tags: list[str] | None = None,
) -> dict[str, Any]:
    """Use OpenAI Responses API to extract suggested tags for a note.

    Encourages reuse by providing taxonomy (existing tag vocabulary)
    and the note's current tags as context. Returns a dict with keys:
      - tags: list[str]
    """
    logger.info("Starting enrichment for note - title: %s, content length: %d",
                title, len(content) if content else 0)

    text = build_note_text(title, content)
    if not text:
        logger.warning("No text content available for enrichment")
        return {"tags": []}

    logger.debug("Built note text: %s", text[:200] + "..." if len(text) > 200 else text)

    client = get_openai_client()

    tag_vocab = (taxonomy.tag_vocab if taxonomy else [])
    existing_tags = [t for t in (existing_tags or []) if isinstance(t, str)]

    logger.debug("Enrichment context - tag_vocab: %s, existing_tags: %s",
                tag_vocab, existing_tags)

    instructions = (
        "You are extracting concise organizational tags from a personal note. "
        "Return JSON only, matching the provided schema.\n"
        "- Prefer reusing existing tags from tag_vocab; only propose a new tag if no suitable existing tag fits.\n"
        "- Reuse or refine the note's existing_tags when appropriate. Keep tags lowercase, max 5.\n"
        "- Tags should be compact hints (dates, people, places, tasks, priority, sources)."
    )

    context = {
        "tag_vocab": tag_vocab,
        "existing_tags": existing_tags,
    }
    composed_input = (
        "NOTE:\n" + text + "\n\n" +
        "CONTEXT:\n" + str(context)
    )

    try:
        logger.info("Making OpenAI API call for enrichment")

        response = await client.responses.parse(
            model=settings.enrichment_model,
            input=[
                {
                    "role": "system",
                    "content": instructions,
                },
                {
                    "role": "user",
                    "content": composed_input,
                }
            ],
            reasoning={ "effort": settings.enrichment_model_reasoning },
            text={ "verbosity": "low" },
            text_format=NoteEnrichmentResult,
        )

        logger.debug("OpenAI response received - has refusal: %s", hasattr(response, "refusal") and response.refusal)

        if hasattr(response, "refusal") and response.refusal:
            logger.warning("OpenAI refused to process the note: %s", response.refusal)
            return {"tags": []}

        result = response.output_parsed
        logger.info("Enrichment successful - result: %s", result)
        logger.debug("Parsed result type: %s, tags: %s",
                    type(result), result.tags if result else None)

        dumped_result = result.model_dump()
        return dumped_result

    except Exception as err:  # pragma: no cover - network/parse errors
        logger.error("Failed to enrich note: %s", err)
        logger.error("Error type: %s", type(err).__name__)
        logger.error("Error details: %s", str(err))
        return {"tags": []}


