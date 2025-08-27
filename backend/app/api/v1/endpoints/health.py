from __future__ import annotations

import asyncio

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from app.config import settings
from app.db.base import create_request_supabase_client

router = APIRouter()


@router.get("/")
async def health_check():
    """Health check endpoint."""
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "status": "healthy",
            "service": "notes-assistant-api",
            "version": "0.1.0"
        }
    )


@router.get("/ready")
async def readiness_check():
    """Readiness check endpoint."""
    db_status = "connected"
    try:
        client = create_request_supabase_client()
        await asyncio.to_thread(lambda: client.table("notes").select("id").limit(1).execute())
    except Exception as e:
        db_status = f"error: {str(e)}"

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "status": "ready",
            "database": db_status,
            "ai_service": "available",
            "cors_origins": settings.cors_origins,
            "api_prefix": settings.api_prefix
        }
    )
