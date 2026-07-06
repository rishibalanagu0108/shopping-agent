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
        # astream_events fires on_chat_model_stream for every chat-model call in the
        # graph run, including input_guardrail's topic-classifier LLM -- scope to the
        # "agent" node only, or the classifier's own tokens leak into the chat reply.
        if kind == "on_chat_model_stream" and event["metadata"].get("langgraph_node") == "agent":
            chunk = event["data"]["chunk"]
            if chunk.content:
                yield _sse("token", chunk.content)
        elif kind == "on_chain_end" and event["name"] == "input_guardrail" and event["data"]["output"].get("blocked"):
            # Blocked turns never reach the agent node, so no LLM ever streams the
            # fallback text -- it's a hardcoded AIMessage. Surface it manually here,
            # the one case where "token" data isn't literally an LLM token.
            yield _sse("token", event["data"]["output"]["messages"][0].content)
        elif kind == "on_tool_start":
            yield _sse("tool_call", {"name": event["name"], "status": "start"})
        elif kind == "on_tool_end":
            # ToolMessage.content is usually the JSON string ToolNode serialized the tool's
            # return value into, but some providers wrap it as a list of content blocks
            # ([{"type": "text", "text": "..."}]) instead of a plain string -- normalize
            # before parsing so the frontend gets real product objects for chips.
            content = event["data"]["output"].content
            if isinstance(content, list):
                content = "".join(b.get("text", "") for b in content if isinstance(b, dict))
            try:
                result = json.loads(content)
            except (json.JSONDecodeError, TypeError):
                result = None
            yield _sse("tool_call", {"name": event["name"], "status": "end", "result": result})

    yield _sse("done", "")


@router.post("/chat")
async def chat(request: ChatRequest):
    return StreamingResponse(_stream_chat(request.user_id, request.message), media_type="text/event-stream")
