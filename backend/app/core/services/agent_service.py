from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import TYPE_CHECKING, Any

from app.background import enrich_and_store_note_tags, generate_and_store_note_embedding
from app.config import settings
from app.core.models.note import NoteType
from app.core.schemas.agent_note import AgentNoteCreate, AgentNoteUpdate
from app.core.schemas.note_search import AgentSearchRequest
from app.core.services.embedding_service import create_embedding
from app.core.services.taxonomy_service import build_user_note_taxonomy
from app.utils.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from uuid import UUID

    from openai import AsyncOpenAI  # type: ignore[import-not-found]

    from app.core.services.note_service import NoteService
    from app.core.services.search_service import SearchService


logger = get_logger(__name__)


class AgentService:
    """RAG agent using GPT-5 with function calling to manage and query notes."""

    def __init__(
        self,
        note_service: NoteService,
        search_service: SearchService,
        openai_client: AsyncOpenAI,
    ) -> None:
        self._note_service = note_service
        self._search_service = search_service
        self._client = openai_client
    def _safe_log_args(self, _tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
        """Sanitize potentially large or sensitive arguments for logging."""
        safe: dict[str, Any] = {}
        for key, value in (args or {}).items():
            if key in {"content"} and isinstance(value, str):
                if len(value) > 200:
                    safe[key] = f"{value[:200]}... ({len(value)} chars)"
                else:
                    safe[key] = value
            else:
                safe[key] = value
        return safe



    async def _dispatch_tool(
        self,
        *,
        name: str,
        args: dict[str, Any],
        user_id: UUID,
        collect_source_ids: set[str],
    ) -> Any:
        logger.debug(
            "Dispatching tool %s with args=%s",
            name,
            json.dumps(self._safe_log_args(name, args)),
            extra={
                "user_id": str(user_id),
                "tool_name": name,
                "arguments": self._safe_log_args(name, args),
            },
        )

        if name == "search_notes":
            allowed = {
                "query", "tags", "match_all_tags", "note_type", "is_archived",
                "limit", "alpha", "created_from", "created_to", "updated_from", "updated_to"
            }
            safe_args = {k: args.get(k) for k in allowed}
            return await self._tool_search_notes(user_id=user_id, **safe_args, collect_source_ids=collect_source_ids)
        if name == "create_note":
            allowed = {"title", "content", "note_type"}
            safe_args = {k: args.get(k) for k in allowed}
            return await self._tool_create_note(user_id=user_id, **safe_args)
        if name == "update_note":
            allowed = {"id", "title", "content", "note_type", "is_archived"}
            safe_args = {k: args.get(k) for k in allowed}
            return await self._tool_update_note(user_id=user_id, **safe_args)
        if name == "delete_note":
            allowed = {"id"}
            safe_args = {k: args.get(k) for k in allowed}
            return await self._tool_delete_note(user_id=user_id, **safe_args)

        logger.warning("Unknown tool requested: %s", name, extra={"user_id": str(user_id), "tool_name": name})
        return {"error": f"Unknown tool: {name}"}

    def _build_tools(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "name": "search_notes",
                "description": "Search user's notes by natural language and optional filters, returning matched notes sorted by relevance.",
                "strict": True,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": ["string", "null"], "description": "Free text query to match in notes"},
                        "tags": {"type": ["array", "null"], "items": {"type": "string"}},
                        "match_all_tags": {"type": ["boolean", "null"], "description": "If true, require all tags to match"},
                        "note_type": {
                            "type": ["string", "null"],
                            "enum": [None, "note", "task", "event", "recipe", "vocabulary"],
                        },
                        "is_archived": {"type": ["boolean", "null"]},
                        "limit": {"type": ["integer", "null"], "minimum": 1, "maximum": 200},
                        "alpha": {"type": ["number", "null"], "minimum": 0, "maximum": 1},
                        "created_from": {"type": ["string", "null"], "format": "date-time"},
                        "created_to": {"type": ["string", "null"], "format": "date-time"},
                        "updated_from": {"type": ["string", "null"], "format": "date-time"},
                        "updated_to": {"type": ["string", "null"], "format": "date-time"},
                    },
                    "required": [
                        "query",
                        "tags",
                        "match_all_tags",
                        "note_type",
                        "is_archived",
                        "limit",
                        "alpha",
                        "created_from",
                        "created_to",
                        "updated_from",
                        "updated_to",
                    ],
                    "additionalProperties": False,
                },
            },
            {
                "type": "function",
                "name": "create_note",
                "description": "Create a new note for the user.",
                "strict": True,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "maxLength": 500},
                        "content": {"type": ["string", "null"], "maxLength": 10000},
                        "note_type": {
                            "type": "string",
                            "enum": ["note", "task", "event", "recipe", "vocabulary"],
                        }
                    },
                    "required": ["title", "content", "note_type"],
                    "additionalProperties": False,
                },
            },
            {
                "type": "function",
                "name": "update_note",
                "description": "Update fields on an existing note by ID.",
                "strict": True,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "title": {"type": ["string", "null"], "maxLength": 500},
                        "content": {"type": ["string", "null"], "maxLength": 10000},
                        "note_type": {
                            "type": "string",
                            "enum": ["note", "task", "event", "recipe", "vocabulary"],
                        },
                        "is_archived": {"type": "boolean"}
                    },
                    "required": ["id", "title", "content", "note_type", "is_archived"],
                    "additionalProperties": False,
                },
            },
            {
                "type": "function",
                "name": "delete_note",
                "description": "Delete a note by ID.",
                "strict": True,
                "parameters": {
                    "type": "object",
                    "properties": {"id": {"type": "string"}},
                    "required": ["id"],
                    "additionalProperties": False,
                },
            },
        ]

    @staticmethod
    def _parse_iso_datetime(value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            v = value.strip()
            if v.endswith("Z"):
                v = v[:-1] + "+00:00"
            return datetime.fromisoformat(v)
        except Exception:
            return None

    def _build_response_kwargs(
        self,
        *,
        tools: list[dict[str, Any]],
        next_inputs: list[Any],
        instructions: str,
        allowed_tools_choice: dict[str, Any],
        previous_response_id: str | None,
    ) -> dict[str, Any]:
        model_name = settings.agent_model
        reasoning_effort = settings.agent_model_reasoning
        text_verbosity = settings.agent_model_text_verbosity

        kwargs: dict[str, Any] = {
            "model": model_name,
            "tools": tools,
            "input": next_inputs,
            "instructions": instructions,
            "reasoning": {"effort": reasoning_effort},
            "text": {"verbosity": text_verbosity},
            "tool_choice": allowed_tools_choice,
            "parallel_tool_calls": True,
            "store": True,
            "truncation": "auto",
        }
        if previous_response_id is not None:
            kwargs["previous_response_id"] = previous_response_id
        return kwargs

    @staticmethod
    def _get_field(obj: Any, key: str) -> Any:
        if isinstance(obj, dict):
            return obj.get(key)
        return getattr(obj, key, None)

    async def _tool_search_notes(
        self,
        *,
        user_id: UUID,
        query: str | None,
        tags: list[str] | None,
        match_all_tags: bool | None,
        note_type: str | None,
        is_archived: bool | None,
        limit: int | None,
        alpha: float | None,
        created_from: str | None,
        created_to: str | None,
        updated_from: str | None,
        updated_to: str | None,
        collect_source_ids: set[str],
    ) -> Any:
        logger.info(
            "Searching notes with args=%s",
            json.dumps({
                "has_query": bool(query),
                "query": (query[:200] + "..." if isinstance(query, str) and len(query) > 200 else query),
                "tags": tags or [],
                "match_all_tags": match_all_tags,
                "note_type": note_type,
                "is_archived": is_archived,
                "limit": limit,
                "alpha": alpha,
                "created_from": created_from,
                "created_to": created_to,
                "updated_from": updated_from,
                "updated_to": updated_to,
            }),
            extra={
            "user_id": str(user_id),
            "has_query": bool(query),
            "query": (query[:200] + "..." if isinstance(query, str) and len(query) > 200 else query),
            "tags": tags or [],
            "match_all_tags": match_all_tags,
            "note_type": note_type,
            "is_archived": is_archived,
            "limit": limit,
            "alpha": alpha,
            "created_from": created_from,
            "created_to": created_to,
            "updated_from": updated_from,
            "updated_to": updated_to,
        })

        query_embedding: list[float] | None = None
        if query:
            try:
                query_embedding = await create_embedding(query)
                logger.debug("Generated query embedding", extra={"user_id": str(user_id), "query_length": len(query)})
            except Exception as err:  # pragma: no cover - network errors
                logger.warning("Embedding failed, falling back to lexical search: %s", err, extra={"user_id": str(user_id)})
                query_embedding = None

        limit_val = max(1, min(int(limit or 20), 200))
        match_all = bool(match_all_tags) if match_all_tags is not None else False
        alpha_val = float(alpha) if alpha is not None else 0.5

        created_from_dt = self._parse_iso_datetime(created_from)
        created_to_dt = self._parse_iso_datetime(created_to)
        updated_from_dt = self._parse_iso_datetime(updated_from)
        updated_to_dt = self._parse_iso_datetime(updated_to)

        results = await self._search_service.search_notes_agent(
            user_id=user_id,
            request=self._make_agent_search_request(
                query=query or None,
                tags=tags or None,
                match_all_tags=match_all,
                note_type=NoteType(note_type) if note_type else None,
                is_archived=is_archived,
                limit=limit_val,
                alpha=alpha_val,
                created_from=created_from_dt,
                created_to=created_to_dt,
                updated_from=updated_from_dt,
                updated_to=updated_to_dt,
            ),
            query_embedding=query_embedding,
        )

        payload = []
        initial_sources_count = len(collect_source_ids)
        for r in results:
            rid = str(r.id)
            collect_source_ids.add(rid)
            payload.append(
                {
                    "id": rid,
                    "title": r.title,
                    "content": r.content,
                    "note_type": r.note_type.value,
                    "tags": r.tags,
                    "rank": r.rank,
                    "created_at": r.created_at.isoformat(),
                    "updated_at": r.updated_at.isoformat() if r.updated_at else None,
                }
            )

        added_sources = len(collect_source_ids) - initial_sources_count
        logger.info(
            "Search completed: count=%d, source_ids_added=%d, ids_sample=%s, titles_sample=%s",
            len(payload),
            added_sources,
            json.dumps([p.get("id") for p in payload[:5]]),
            json.dumps([p.get("title") for p in payload[:3]]),
            extra={
                "user_id": str(user_id),
                "result_count": len(payload),
                "source_ids_added": added_sources,
                "result_ids_sample": [p.get("id") for p in payload[:5]],
                "top_titles_sample": [p.get("title") for p in payload[:3]],
            },
        )
        return {"results": payload}


    async def _tool_create_note(
        self,
        *,
        user_id: UUID,
        title: str | None,
        content: str | None,
        note_type: str | None,
    ) -> Any:
        logger.info("Creating note", extra={
            "user_id": str(user_id),
            "note_type": note_type,
            "has_title": bool(title),
            "content_length": len(content) if content else 0,
        })

        create_dto = AgentNoteCreate(
            title=title,
            content=content,
            note_type=(NoteType(note_type) if note_type else NoteType.NOTE),
            tags=None,
            is_archived=False,
        )
        created = await self._note_service.create_note(create_dto, user_id)
        logger.info("Note created successfully", extra={"user_id": str(user_id), "note_id": str(created.id)})

        asyncio.create_task(
            generate_and_store_note_embedding(
                note_id=created.id,
                title=created.title,
                content=created.content,
            )
        )
        asyncio.create_task(
            enrich_and_store_note_tags(
                note_id=created.id,
                user_id=user_id,
                title=created.title,
                content=created.content,
            )
        )
        return {"status": "success", "id": str(created.id)}

    async def _tool_update_note(
        self,
        *,
        user_id: UUID,
        id: str,
        title: str | None = None,
        content: str | None = None,
        note_type: str | None = None,
        is_archived: bool | None = None,
    ) -> Any:
        logger.info("Updating note", extra={
            "user_id": str(user_id),
            "note_id": id,
            "fields_updated": [k for k, v in [("title", title), ("content", content), ("note_type", note_type), ("is_archived", is_archived)] if v is not None],
        })

        update_dto = AgentNoteUpdate(
            title=title,
            content=content,
            note_type=(NoteType(note_type) if note_type else None),
            is_archived=is_archived,
        )
        updated = await self._note_service.update_note(id, update_dto, user_id)
        if not updated:
            logger.warning("Note not found for update", extra={"user_id": str(user_id), "note_id": id})
            return {"status": "not_found"}

        asyncio.create_task(
            generate_and_store_note_embedding(
                note_id=updated.id,
                title=updated.title,
                content=updated.content,
            )
        )
        asyncio.create_task(
            enrich_and_store_note_tags(
                note_id=updated.id,
                user_id=user_id,
                title=updated.title,
                content=updated.content,
            )
        )

        logger.info("Note updated successfully", extra={"user_id": str(user_id), "note_id": str(updated.id)})
        return {"status": "success", "id": str(updated.id)}

    async def _tool_delete_note(
        self,
        *,
        user_id: UUID,
        id: str,
    ) -> Any:
        logger.info("Deleting note", extra={"user_id": str(user_id), "note_id": id})

        ok = await self._note_service.delete_note(id, user_id)
        if ok:
            logger.info("Note deleted successfully", extra={"user_id": str(user_id), "note_id": id})
        else:
            logger.warning("Note not found for deletion", extra={"user_id": str(user_id), "note_id": id})

        return {"status": "success" if ok else "not_found"}

    def _make_agent_search_request(
        self,
        *,
        query: str | None,
        tags: list[str] | None,
        match_all_tags: bool,
        note_type: NoteType | None,
        is_archived: bool | None,
        limit: int,
        alpha: float,
        created_from,
        created_to,
        updated_from,
        updated_to,
    ) -> AgentSearchRequest:

        return AgentSearchRequest(
            query=query,
            tags=tags,
            match_all_tags=match_all_tags,
            note_type=note_type,
            is_archived=is_archived,
            limit=limit,
            alpha=alpha,
            created_from=created_from,
            created_to=created_to,
            updated_from=updated_from,
            updated_to=updated_to,
        )




    async def chat_stream(
        self,
        *,
        user_id: UUID,
        message: str,
        previous_response_id: str | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Stream only actions (function calls) and the final assistant response.

        Yields dict events of shape:
        - {"type": "tool_call", "name": str, "arguments": dict}
        - {"type": "tool_result", "name": str}
        - {"type": "final", "response": str, "sources": list[str], "response_id": str | None}
        - {"type": "error", "message": str}
        """
        logger.info("Starting streaming chat session", extra={"user_id": str(user_id), "message_length": len(message)})

        tools = self._build_tools()
        allowed_tools_choice = {
            "type": "allowed_tools",
            "mode": "auto",
            "tools": [{"type": "function", "name": t.get("name", "")} for t in tools if t.get("type") == "function"],
        }

        try:
            taxonomy = await build_user_note_taxonomy(user_id=user_id)
            known_tags = taxonomy.tag_vocab
        except Exception:
            known_tags = []
            logger.warning("Failed to retrieve user taxonomy", extra={"user_id": str(user_id)})

        note_types = [t.value for t in NoteType]
        instructions = (
            "You are a helpful personal notes assistant.\n"
            "- Use tools to search and manage notes.\n"
            "- Prefer searching relevant notes before answering.\n"
            "- Keep answers concise and accurate.\n"
            "- When your answer uses notes, try to cite them.\n"
            f"- Available note types: {', '.join(note_types)}.\n"
            f"- Known user tags (normalized): {', '.join(known_tags) if known_tags else 'none'}.\n"
            "- For search, you can set: query, tags (subset of known tags), match_all_tags, note_type, is_archived, limit, alpha (0..1), created_from, created_to, updated_from, updated_to (ISO 8601).\n"
            "- Default alpha is 0.5 if not provided.\n\n"
            "<search_param_priorities>\n"
            "- Prefer tags when the user's request clearly matches Known user tags (case-insensitive). If multiple distinct matched tags exist, set match_all_tags=true.\n"
            "- If there is no clear tag match, prefer using query with the user's natural-language request; set tags=null and match_all_tags=false.\n"
            "- Avoid setting note_type by default. Only set note_type when the user explicitly asks for a specific type (e.g., 'tasks', 'events') or when the intent is unmistakable. Otherwise leave it null.\n"
            "- Keep limit modest (e.g., 30) unless the user asks for more.\n"
            "</search_param_priorities>\n\n"
            "\n"
            "<context_gathering>\n"
            "- Prefer 1 tool round; absolute max 3. Stop as soon as you can answer confidently.\n"
            "- If you’re unsure, ask a concise clarifying question instead of calling a tool.\n"
            "</context_gathering>\n\n"
            "<tool_preambles>\n"
            "- Before each tool call, explain in one short sentence what you’re doing and why.\n"
            "</tool_preambles>\n\n"
            "<tool_calling_rules>\n"
            "- Arguments MUST match the schema exactly:\n"
            "  - Include only allowed keys; set unknowns to null; correct types only.\n"
            "  - Respect bounds: limit ∈ [1, 200], alpha ∈ [0, 1]; dates in ISO 8601.\n"
            "- Do not invent IDs, tags, or note_type values. Only use values present in prior tool results or user input.\n"
            "- Prefer a single search_notes call first; avoid repeated searches unless the user’s request changes materially.\n"
            "- If a tool returns an error or empty result, do not repeat the same call; adjust once (e.g., try to relax constraints, change query or tags, increase limit). If still not useful, finalize with an explanation instead of more tool calls.\n"
            "- When multiple independent calls are required, batch them in parallel; otherwise keep to a single call.\n"
            "</tool_calling_rules>\n\n"
            "<early_stop>\n"
            "- Stop tool use immediately when you can produce a concise, correct final answer.\n"
            "</early_stop>\n"
            "Today is " + datetime.now().strftime("%A, %Y-%m-%d at %H:%M")
        )

        next_inputs: list[Any] = [{"role": "user", "content": message}]
        collected_source_ids: set[str] = set()

        # Up to 3 tool execution rounds, then finalize
        for turn in range(3):
            logger.debug("[stream] Agent turn %d", turn + 1, extra={"user_id": str(user_id), "turn": turn + 1})
            try:
                create_kwargs = self._build_response_kwargs(
                    tools=tools,
                    next_inputs=next_inputs,
                    instructions=instructions,
                    allowed_tools_choice=allowed_tools_choice,
                    previous_response_id=previous_response_id,
                )
                response = await self._client.responses.create(**create_kwargs)
            except Exception as err:  # pragma: no cover - network errors
                logger.error("Responses API call failed (stream mode): %s", err, extra={"user_id": str(user_id)})
                yield {"type": "error", "message": "I'm unable to complete that request right now. Please try again."}
                return

            previous_response_id = getattr(response, "id", None)
            output_items = response.output or []

            pending_tool_calls = [item for item in output_items if self._get_field(item, "type") == "function_call"]
            if not pending_tool_calls:
                # Final answer – stream tokens via Responses streaming API
                logger.info("[stream] Finalizing with streamed output", extra={
                    "user_id": str(user_id),
                    "turns": turn + 1,
                    "source_count": len(collected_source_ids),
                })
                # Inform client to prepare for final streaming
                yield {"type": "final_start"}

                try:
                    # Use the previous response context if set; otherwise stream a fresh turn
                    stream_kwargs = self._build_response_kwargs(
                        tools=tools,
                        next_inputs=next_inputs or [{"role": "user", "content": message}],
                        instructions=instructions,
                        allowed_tools_choice=allowed_tools_choice,
                        previous_response_id=previous_response_id,
                    )

                    async with self._client.responses.stream(**stream_kwargs) as stream:  # type: ignore[attr-defined]
                        async for event in stream:
                            etype = getattr(event, "type", None)
                            if etype is None and isinstance(event, dict):
                                etype = event.get("type")

                            if etype == "response.output_text.delta":
                                delta = getattr(event, "delta", None)
                                if delta is None and isinstance(event, dict):
                                    delta = event.get("delta")
                                if delta:
                                    yield {"type": "final_delta", "delta": str(delta)}
                            elif etype == "response.error":  # pragma: no cover - defensive
                                # Best-effort error propagation
                                msg = getattr(event, "error", None)
                                if isinstance(msg, dict):
                                    msg = msg.get("message")
                                yield {"type": "error", "message": str(msg or "Streaming failed.")}
                            elif etype == "response.completed":
                                final_resp = getattr(event, "response", None)
                                rid = None
                                if final_resp is not None:
                                    rid = getattr(final_resp, "id", None)
                                    if rid is None and isinstance(final_resp, dict):
                                        rid = final_resp.get("id")
                                previous_response_id = rid or previous_response_id
                                # Signal completion (no text payload; UI has built it incrementally)
                                yield {
                                    "type": "final_done",
                                    "sources": sorted(collected_source_ids),
                                    "response_id": previous_response_id,
                                }
                                return
                except Exception as err:  # pragma: no cover - network errors
                    logger.error("Responses API stream failed: %s", err, extra={"user_id": str(user_id)})
                    try:
                        fallback_resp = await self._client.responses.create(**stream_kwargs)
                        text = getattr(fallback_resp, "output_text", None)
                        if not text:
                            # Defensive: minimal extraction from output items
                            output_items = getattr(fallback_resp, "output", None) or []
                            try:
                                text = "".join(
                                    [getattr(it, "text", "") if not isinstance(it, dict) else (it.get("text") or "") for it in output_items]
                                )
                            except Exception:
                                text = None
                        if not text:
                            text = "I'm unable to complete that request right now. Please try again."
                        rid = getattr(fallback_resp, "id", None)
                        previous_response_id = rid or previous_response_id
                        yield {
                            "type": "final",
                            "response": str(text),
                            "sources": sorted(collected_source_ids),
                            "response_id": previous_response_id,
                        }
                        return
                    except Exception as err2:  # pragma: no cover - network errors
                        logger.error("Non-streamed fallback failed: %s", err2, extra={"user_id": str(user_id)})
                        yield {"type": "error", "message": "We couldn't complete the request. Please try again."}
                        return

            logger.info("[stream] Executing %d tool calls", len(pending_tool_calls), extra={
                "user_id": str(user_id),
                "turn": turn + 1,
                "tool_count": len(pending_tool_calls),
            })

            # Prepare next inputs from tool outputs
            next_inputs = []
            for tool_call in pending_tool_calls:
                try:
                    name: str = self._get_field(tool_call, "name") or ""
                    raw_args = self._get_field(tool_call, "arguments") or "{}"
                    args: dict[str, Any] = json.loads(raw_args)
                except Exception:
                    name = self._get_field(tool_call, "name") or ""
                    args = {}

                # Stream the tool call event (action)
                call_id = self._get_field(tool_call, "call_id")
                yield {"type": "tool_call", "name": name, "arguments": args, "call_id": call_id}

                # Execute tool
                try:
                    result: Any = await self._dispatch_tool(
                        name=name,
                        args=args,
                        user_id=user_id,
                        collect_source_ids=collected_source_ids,
                    )
                except Exception as err:  # pragma: no cover - defensive
                    logger.error("Tool execution failed: %s", err, extra={"user_id": str(user_id), "tool_name": name})
                    result = {"error": str(err)}

                # Stream completion of tool call
                yield {"type": "tool_result", "name": name, "call_id": call_id}

                # Add tool output for the next model turn
                next_inputs.append(
                    {
                        "type": "function_call_output",
                        "call_id": call_id,
                        "output": json.dumps(result),
                    }
                )

                try:
                    summary: dict[str, Any] | None = None
                    if name == "search_notes" and isinstance(result, dict):
                        res_list = result.get("results") or []
                        if isinstance(res_list, list):
                            summary = {
                                "count": len(res_list),
                                "ids_sample": [r.get("id") for r in res_list[:5]],
                                "titles_sample": [r.get("title") for r in res_list[:3]],
                            }
                    elif name in {"create_note", "update_note", "delete_note"} and isinstance(result, dict):
                        summary = {
                            "status": result.get("status"),
                            "id": result.get("id"),
                        }
                    logger.info(
                        "Tool call completed: %s (call_id=%s) summary=%s",
                        name,
                        str(call_id),
                        json.dumps(summary),
                        extra={
                            "user_id": str(user_id),
                            "tool_name": name,
                            "call_id": call_id,
                            "result_summary": summary,
                        },
                    )
                except Exception:  # pragma: no cover - defensive
                    logger.warning("Failed to summarize tool result for logging", extra={"user_id": str(user_id), "tool_name": name})

        # Fallback finalization if exceeded max turns
        logger.warning("[stream] Agent exceeded max turns, using fallback", extra={"user_id": str(user_id)})
        fail_safe = "I'm unable to complete that request right now. Please try again."
        yield {"type": "final_start"}
        try:
            stream_kwargs = self._build_response_kwargs(
                tools=self._build_tools(),
                next_inputs=next_inputs,
                instructions=instructions,
                allowed_tools_choice=allowed_tools_choice,
                previous_response_id=previous_response_id,
            )

            async with self._client.responses.stream(**stream_kwargs) as stream:  # type: ignore[attr-defined]
                async for event in stream:
                    etype = getattr(event, "type", None)
                    if etype is None and isinstance(event, dict):
                        etype = event.get("type")
                    if etype == "response.output_text.delta":
                        delta = getattr(event, "delta", None)
                        if delta is None and isinstance(event, dict):
                            delta = event.get("delta")
                        if delta:
                            yield {"type": "final_delta", "delta": str(delta)}
                    elif etype == "response.completed":
                        final_resp = getattr(event, "response", None)
                        rid = None
                        if final_resp is not None:
                            rid = getattr(final_resp, "id", None)
                            if rid is None and isinstance(final_resp, dict):
                                rid = final_resp.get("id")
                        previous_response_id = rid or previous_response_id
                        yield {
                            "type": "final_done",
                            "sources": sorted(collected_source_ids),
                            "response_id": previous_response_id,
                        }
                        return
        except Exception:  # pragma: no cover - network errors
            logger.error("Failed to get fallback streamed response (stream mode)", extra={"user_id": str(user_id)})
            yield {"type": "final", "response": fail_safe, "sources": sorted(collected_source_ids), "response_id": previous_response_id}
        return
