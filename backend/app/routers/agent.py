import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from pydantic import BaseModel

from app.agent.graph import graph
from app.agent.memory import load_session_intro, trim_messages

router = APIRouter(prefix="/api/agent", tags=["agent"])

# Per-user_id short-term conversation history. In-memory and lost on restart on purpose --
# durable cross-session facts already go through update_long_term_memory into SQLite;
# this is just the sliding window trim_messages was built for, finally given something to
# trim. Each POST used to start a graph run from scratch (intro + only the new message),
# so multi-turn coreference ("add the one you just mentioned") had nothing to resolve
# against -- this dict is what carries prior turns across separate HTTP requests.
_sessions: dict[int, list[BaseMessage]] = {}


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
    history = _sessions.get(user_id)
    if history is None:
        history = [await load_session_intro(user_id)]

    human_message = HumanMessage(content=message)
    inputs = {
        "messages": history + [human_message],
        "user_id": user_id,
        "cart_snapshot": [],
        "last_products": [],
        "blocked": False,
    }

    # Buffer the agent's text instead of forwarding on_chat_model_stream tokens live --
    # streaming raw tokens would put them in front of the user before output_guardrail
    # (which only runs after the "agent" node fully finishes) gets a chance to swap a
    # hallucinated reply for the safe fallback. Wait for output_guardrail's on_chain_end
    # and emit whatever it decided is the final text, corrected or not.
    agent_reply = ""
    final_reply = None
    async for event in graph.astream_events(inputs, version="v2"):
        kind = event["event"]
        if kind == "on_chain_end" and event["name"] == "agent":
            msgs = event["data"]["output"].get("messages") or []
            if msgs and msgs[0].content:
                agent_reply = msgs[0].content
        elif kind == "on_chain_end" and event["name"] == "output_guardrail":
            corrected = event["data"]["output"].get("messages")
            final_reply = corrected[0].content if corrected else agent_reply
            yield _sse("token", final_reply)
        elif kind == "on_chain_end" and event["name"] == "input_guardrail" and event["data"]["output"].get("blocked"):
            # Blocked turns never reach the agent node, so no LLM ever streams the
            # fallback text -- it's a hardcoded AIMessage. Surface it manually here,
            # the one case where "token" data isn't literally an LLM token.
            final_reply = event["data"]["output"]["messages"][0].content
            yield _sse("token", final_reply)
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

    history.append(human_message)
    if final_reply is not None:
        history.append(AIMessage(content=final_reply))
    _sessions[user_id] = trim_messages(history)

    yield _sse("done", "")


@router.post("/chat")
async def chat(request: ChatRequest):
    return StreamingResponse(_stream_chat(request.user_id, request.message), media_type="text/event-stream")
