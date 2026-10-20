import asyncio
from typing import Annotated

from fastapi import Header, Request

from pharmacy_core.conversation.models import ConversationView


from fastapi import APIRouter
from pharmacy_core.api.dependencies import bearer, conversation_store

router = APIRouter()


@router.post("/conversation", response_model=ConversationView)
async def new_conversation(request: Request):
    return await asyncio.to_thread(conversation_store(request).create)


@router.get("/conversation", response_model=ConversationView)
async def restore_conversation(request: Request, authorization: Annotated[str | None, Header()] = None):
    return await asyncio.to_thread(conversation_store(request).restore, bearer(authorization))


@router.delete("/conversation", status_code=204)
async def reset_conversation(request: Request, authorization: Annotated[str | None, Header()] = None):
    await asyncio.to_thread(conversation_store(request).reset, bearer(authorization))
