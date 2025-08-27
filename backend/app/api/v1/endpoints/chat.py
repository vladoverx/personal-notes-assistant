from __future__ import annotations

import json
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.api.v1.schemas.chat import ChatRequest  # noqa: TCH001
from app.dependencies import get_agent_service, get_current_user

if TYPE_CHECKING:
    from app.core.schemas.auth import AuthUser
    from app.core.services.agent_service import AgentService

router = APIRouter()

@router.post("/stream")
async def chat_with_assistant_stream(
    payload: ChatRequest,
    current_user: AuthUser = Depends(get_current_user),
    agent: AgentService = Depends(get_agent_service),
):
    """Stream tool-call actions and the final assistant message via SSE."""

    async def event_iterator():
        try:
            async for evt in agent.chat_stream(
                user_id=current_user.id,
                message=payload.message,
                previous_response_id=payload.previous_response_id,
            ):
                event_type = evt.get("type", "message")
                data = json.dumps(evt)
                yield f"event: {event_type}\n"
                yield f"data: {data}\n\n"
        except Exception:
            fallback = {"type": "error", "message": "Streaming failed."}
            yield "event: error\n"
            yield f"data: {json.dumps(fallback)}\n\n"

    return StreamingResponse(
        event_iterator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
