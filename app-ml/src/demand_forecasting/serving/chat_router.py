import hashlib
import json
import logging
import traceback

from fastapi import APIRouter, Header
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from demand_forecasting.serving.chat.graph import app

logger = logging.getLogger(__name__)
chat_router = APIRouter()


class ChatRequest(BaseModel):
    """Payload schema for streaming chat requests."""

    messages: list[dict]
    thread_id: str


@chat_router.post("/stream")
async def stream_chat(
    request: ChatRequest,
    # The actual Argon2 security validation is rigorously enforced by model_server.py via `Depends` at the router integration level.
    # We just extract the raw header here to pass directly into the LangGraph state for backend-to-backend API authentication.
    x_api_key: str = Header(..., description="API Key for Authorization"),
) -> StreamingResponse:
    """Stream multi-agent reasoning and responses via Server-Sent Events."""

    async def event_generator():
        # Scope thread_id to caller API key digest so distinct callers never share chat state
        caller_scope = hashlib.sha256(x_api_key.encode("utf-8")).hexdigest()[:16]
        scoped_thread_id = f"{caller_scope}:{request.thread_id}"
        config = {"configurable": {"thread_id": scoped_thread_id}}

        try:
            async for event in app.astream_events(
                {
                    "messages": request.messages,
                    "user_auth_token": x_api_key,  # Secure state injection
                },
                config=config,
                version="v2",
            ):
                if event["event"] == "on_chat_model_stream":
                    chunk = event.get("data", {}).get("chunk")
                    if chunk and hasattr(chunk, "content") and chunk.content:
                        payload = {
                            "event": "on_chat_model_stream",
                            "data": {"chunk": {"content": str(chunk.content)}},
                        }
                        yield f"data: {json.dumps(payload)}\n\n"

            yield "data: [DONE]\n\n"
        except Exception as e:
            logger.error(f"Stream error: {traceback.format_exc()}")
            yield f"data: {json.dumps({'error': repr(e)})}\n\n"

    # X-Accel-Buffering: no explicitly instructs Nginx reverse proxies not to buffer the stream, maintaining real-time latency
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
