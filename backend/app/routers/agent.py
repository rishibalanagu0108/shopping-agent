import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage
from pydantic import BaseModel

from app.agent.graph import graph
from app.agent.memory import load_session_intro

router = APIRouter(prefix="/api/agent", tags=["agent"])


class ChatRequest(BaseModel):
    user_id: int
    message: str


def _sse(event_type: str, data) -> str:
    return f"data: {json.dumps({'type': event_type, 'data': data})}\n\n"


# SSE over WebSocket: this is one-directional (server pushes tokens/tool events for a
# single request-response, client never sends mid-stream), so plain HTTP + auto-reconnect
# + reuse of the same fetch stack as the REST endpoints beats a WebSocket's separate
# connection lifecycle and protocol upgrade for what's ultimately a glorified long-poll.
async def _stream_chat(user_id: int, message: str):
    intro = await load_session_intro(user_id)
    inputs = {
        "messages": [intro, HumanMessage(content=message)],
        "user_id": user_id,
        "cart_snapshot": [],
        "last_products": [],
        "blocked": False,
    }

    async for event in graph.astream_events(inputs, version="v2"):
        kind = event["event"]
        if kind == "on_chat_model_stream":
            chunk = event["data"]["chunk"]
            if chunk.content:
                yield _sse("token", chunk.content)
        elif kind == "on_tool_start":
            yield _sse("tool_call", event["name"])

    yield _sse("done", "")


@router.post("/chat")
async def chat(request: ChatRequest):
    return StreamingResponse(_stream_chat(request.user_id, request.message), media_type="text/event-stream")
