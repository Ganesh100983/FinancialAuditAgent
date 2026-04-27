import json
import logging
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address

from backend.auth import get_current_user, CurrentUser
from backend.session_store import get_session
from backend.config import get_settings

router = APIRouter(prefix="/chat", tags=["AI Assistant"])
logger = logging.getLogger("financial_audit.chat")
limiter = Limiter(key_func=get_remote_address)


class ChatRequest(BaseModel):
    message: str
    agent_type: str = "ledger"  # ledger | form16 | gst


def _build_agent(agent_type: str, api_key: str, store: dict):
    if not api_key:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "OpenAI API key not configured in Settings.")

    if agent_type == "ledger":
        from src.agents.ledger_agent import create_ledger_agent
        return create_ledger_agent(api_key, store)
    elif agent_type == "form16":
        from src.agents.form16_agent import create_form16_agent
        return create_form16_agent(api_key, store)
    elif agent_type == "gst":
        from src.agents.gst_agent import create_gst_agent
        return create_gst_agent(api_key, store)
    else:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Unknown agent type: {agent_type}")


async def _stream_agent(agent, query: str):
    """Yield SSE-formatted events from the LangGraph agent."""
    try:
        async for event in agent.astream_events(
            {"messages": [("human", query)]},
            version="v2",
        ):
            kind = event.get("event", "")
            name = event.get("name", "")

            if kind == "on_tool_start":
                yield f"data: {json.dumps({'type': 'tool_start', 'tool': name})}\n\n"

            elif kind == "on_tool_end":
                yield f"data: {json.dumps({'type': 'tool_end', 'tool': name})}\n\n"

            elif kind == "on_chat_model_stream":
                chunk = event["data"].get("chunk")
                if chunk and hasattr(chunk, "content") and chunk.content:
                    yield f"data: {json.dumps({'type': 'token', 'content': chunk.content})}\n\n"

    except Exception as exc:
        logger.exception("Agent stream error: %s", exc)
        yield f"data: {json.dumps({'type': 'error', 'content': str(exc)})}\n\n"

    yield f"data: {json.dumps({'type': 'done'})}\n\n"


@router.post("/stream")
@limiter.limit("10/minute")
async def stream_chat(
    request: Request,
    body: ChatRequest,
    user: CurrentUser = Depends(get_current_user),
):
    store = get_session(user.session_id)
    api_key = store.get("openai_api_key") or get_settings().openai_api_key
    agent = _build_agent(body.agent_type, api_key, store)
    logger.info("Chat stream: user=%s agent=%s", user.username, body.agent_type)

    return StreamingResponse(
        _stream_agent(agent, body.message),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


class SettingsUpdateRequest(BaseModel):
    openai_api_key: str = ""


@router.put("/settings")
async def update_settings(req: SettingsUpdateRequest, user: CurrentUser = Depends(get_current_user)):
    store = get_session(user.session_id)
    if req.openai_api_key:
        store["openai_api_key"] = req.openai_api_key
    return {"message": "Settings updated successfully", "openai_api_key_set": bool(store.get("openai_api_key"))}


@router.get("/settings")
async def get_user_settings(user: CurrentUser = Depends(get_current_user)):
    store = get_session(user.session_id)
    return {
        "openai_api_key_set": bool(store.get("openai_api_key")),
        "company_name": store.get("company_name", ""),
        "company_gstin": store.get("company_gstin", ""),
        "company_tan": store.get("company_tan", ""),
        "company_pan": store.get("company_pan", ""),
        "financial_year": store.get("financial_year", "2024-25"),
    }
