from __future__ import annotations

from fastapi import APIRouter

from .endpoints import auth, chat, health, notes, taxonomy

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(notes.router, prefix="/notes", tags=["notes"])
api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
api_router.include_router(taxonomy.router, prefix="/metadata", tags=["metadata"])
