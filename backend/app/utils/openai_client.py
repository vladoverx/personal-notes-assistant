from __future__ import annotations

from functools import lru_cache

from openai import AsyncOpenAI

from app.config import settings
from app.utils.logging import get_logger


@lru_cache(maxsize=1)
def get_openai_client() -> AsyncOpenAI:
    """Return a singleton OpenAI client.

    Uses the environment's OPENAI_API_KEY by default. If `APP_OPENAI_API_KEY` is
    provided in the application's settings, it will be used explicitly.
    """
    logger = get_logger(__name__)
    if settings.openai_api_key:
        logger.debug("Initializing OpenAI client with APP_OPENAI_API_KEY")
        return AsyncOpenAI(api_key=settings.openai_api_key)
    logger.debug("Initializing OpenAI client with default OPENAI_API_KEY from environment")
    return AsyncOpenAI()


