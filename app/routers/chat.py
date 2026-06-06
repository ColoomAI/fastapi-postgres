"""Streaming chat route — example of the single-process agent pattern.

Returns text/event-stream (NOT the Envelope[T] JSON envelope — SSE is
a different content-type by design; envelope only makes sense for
one-shot JSON responses).

Auth-gated via the cookie session (Depends(get_current_user)) — same
as every other protected route. The agent itself doesn't see the user;
add user-id to the prompt or log it if you need per-user usage
tracking.
"""
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.agents.simple import run_agent
from app.deps.auth import CurrentUser, get_current_user

router = APIRouter()


class ChatIn(BaseModel):
    prompt: str = Field(min_length=1, max_length=8_000)


@router.post("/chat")
async def chat(
    payload: ChatIn,
    _user: CurrentUser = Depends(get_current_user),
) -> StreamingResponse:
    return StreamingResponse(
        run_agent(payload.prompt),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",  # nginx + ALB: don't buffer
            "Connection": "keep-alive",
        },
    )
