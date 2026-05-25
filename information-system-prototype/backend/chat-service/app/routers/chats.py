"""Chat endpoints (FR12, FR16–FR19).

Every endpoint is scoped to the authenticated caller: a chat is only visible and
mutable by its owner (`Chat.user_id == principal.user_id`); a foreign or missing
chat returns 404 (existence is not leaked). Sending a message generates an
assistant reply grounded in the local ESCO context and persists both turns.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import get_session
from app.deps import Principal, get_current_user
from app.models import Chat, Message
from app.schemas import (
    ChatCreate,
    ChatDetail,
    ChatListItem,
    MessageOut,
    MessageResponse,
    Page,
    SendMessageRequest,
    SendMessageResponse,
)
from app.services import chats as chat_svc
from app.services.llm import llm

router = APIRouter(prefix="/api", tags=["chats"])

_NOT_FOUND = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")


async def _owned_chat(
    session: AsyncSession, chat_id: int, user_id: int, *, with_messages: bool = False
) -> Chat:
    stmt = select(Chat).where(Chat.id == chat_id, Chat.user_id == user_id)
    if with_messages:
        stmt = stmt.options(selectinload(Chat.messages))
    chat = (await session.execute(stmt)).scalar_one_or_none()
    if chat is None:
        raise _NOT_FOUND
    return chat


# --------------------------------------------------------------------------- #
#  List chats (FR16)
# --------------------------------------------------------------------------- #
@router.get("/chats", response_model=Page[ChatListItem])
async def list_chats(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    principal: Principal = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Page[ChatListItem]:
    total = await session.scalar(
        select(func.count()).select_from(Chat).where(Chat.user_id == principal.user_id)
    )
    rows = await session.execute(
        select(Chat)
        .where(Chat.user_id == principal.user_id)
        .order_by(Chat.updated_at.desc(), Chat.id.desc())
        .limit(page_size)
        .offset((page - 1) * page_size)
    )
    items = [ChatListItem.model_validate(c) for c in rows.scalars().all()]
    return Page[ChatListItem](items=items, page=page, page_size=page_size, total=total or 0)


# --------------------------------------------------------------------------- #
#  Create a chat (FR17) — free or bound to a profession (FR12)
# --------------------------------------------------------------------------- #
@router.post("/chats", response_model=ChatDetail, status_code=status.HTTP_201_CREATED)
async def create_chat(
    payload: ChatCreate,
    principal: Principal = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ChatDetail:
    default_label: str | None = None
    if payload.profession_id is not None:
        # Grounding requires the profession to be in the local copy (from the bus).
        prof = await chat_svc.get_cached_profession(session, payload.profession_id)
        if prof is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Profession not found in the local catalogue",
            )
        default_label = prof.preferred_label

    title = (payload.title or "").strip()
    if not title:
        title = f"About {default_label}" if default_label else "New chat"

    chat = Chat(user_id=principal.user_id, title=title[:255], profession_id=payload.profession_id)
    session.add(chat)
    await session.commit()
    await session.refresh(chat)
    # A new chat has no messages; build the DTO explicitly to avoid a lazy load
    # of the (unloaded) `messages` relationship in async context.
    return ChatDetail(
        id=chat.id,
        title=chat.title,
        profession_id=chat.profession_id,
        created_at=chat.created_at,
        updated_at=chat.updated_at,
        messages=[],
    )


# --------------------------------------------------------------------------- #
#  Get a chat with its messages (FR16)
# --------------------------------------------------------------------------- #
@router.get("/chats/{chat_id}", response_model=ChatDetail)
async def get_chat(
    chat_id: int,
    principal: Principal = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ChatDetail:
    chat = await _owned_chat(session, chat_id, principal.user_id, with_messages=True)
    return ChatDetail.model_validate(chat)


# --------------------------------------------------------------------------- #
#  Send a message → assistant reply (FR18)
# --------------------------------------------------------------------------- #
@router.post("/chats/{chat_id}/messages", response_model=SendMessageResponse)
async def send_message(
    chat_id: int,
    payload: SendMessageRequest,
    principal: Principal = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> SendMessageResponse:
    chat = await _owned_chat(session, chat_id, principal.user_id, with_messages=True)

    # Assemble the grounded prompt from the local ESCO context.
    profession = await chat_svc.get_cached_profession(session, chat.profession_id)
    user = await chat_svc.get_cached_user(session, principal.user_id)
    system_prompt = chat_svc.build_system_prompt(profession, user)
    content = payload.content.strip()
    openai_messages = chat_svc.to_openai_messages(system_prompt, list(chat.messages), content)

    reply = await llm.complete(openai_messages)

    user_msg = Message(chat_id=chat.id, role="user", content=content)
    assistant_msg = Message(chat_id=chat.id, role="assistant", content=reply)
    session.add_all([user_msg, assistant_msg])
    # Bump the chat so it floats to the top of the list.
    chat.updated_at = datetime.now(timezone.utc)
    await session.flush()
    await session.refresh(user_msg)
    await session.refresh(assistant_msg)
    await session.commit()

    return SendMessageResponse(
        user_message=MessageOut.model_validate(user_msg),
        assistant_message=MessageOut.model_validate(assistant_msg),
    )


# --------------------------------------------------------------------------- #
#  Delete a chat (FR19)
# --------------------------------------------------------------------------- #
@router.delete("/chats/{chat_id}", response_model=MessageResponse)
async def delete_chat(
    chat_id: int,
    principal: Principal = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> MessageResponse:
    chat = await _owned_chat(session, chat_id, principal.user_id)
    await session.delete(chat)  # messages cascade (ondelete=CASCADE)
    await session.commit()
    return MessageResponse(detail="Chat deleted")
