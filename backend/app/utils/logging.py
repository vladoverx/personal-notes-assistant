from __future__ import annotations

import logging
import sys

from app.config import settings


def setup_logging() -> None:
    """Setup basic logging for the application."""

    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        stream=sys.stdout
    )

    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)
    logging.getLogger("fastapi").setLevel(logging.INFO)

    logging.info("Logging configured successfully", extra={"level": settings.log_level})


def get_logger(name: str | None = None) -> logging.Logger:
    """Get a logger instance."""
    return logging.getLogger(name)
