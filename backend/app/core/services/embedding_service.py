from __future__ import annotations

from app.utils.logging import get_logger
from app.utils.openai_client import get_openai_client

logger = get_logger(__name__)

EMBEDDING_MODEL = "text-embedding-3-small"  # 1536 dims, per OpenAI docs


def build_note_text(title: str | None, content: str | None) -> str:
    """Concatenate title and content into a single string for embeddings.

    Keeps a stable delimiter so updates result in stable text shape.
    """
    safe_title = (title or "").strip()
    safe_content = (content or "").strip()
    if safe_title and safe_content:
        return f"{safe_title}\n\n{safe_content}"
    return safe_title or safe_content


async def create_embedding(input_text: str) -> list[float] | None:
    """Create an embedding vector for the given text using OpenAI async client."""
    if not input_text:
        return None

    client = get_openai_client()
    try:
        resp = await client.embeddings.create(model=EMBEDDING_MODEL, input=input_text)
        # OpenAI returns list[float] directly, no need for complex type handling
        return resp.data[0].embedding
    except Exception as err:  # pragma: no cover - network errors
        logger.error("Failed to create embedding: %s", err)
        return None


