"""Pydantic v2 DTOs for chat-service."""
from __future__ import annotations

from datetime import datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


# --------------------------------------------------------------------------- #
#  Shared
# --------------------------------------------------------------------------- #
class MessageResponse(BaseModel):
    detail: str


class Page(BaseModel, Generic[T]):
    """Paginated response: {items, page, page_size, total}."""

    items: list[T]
    page: int
    page_size: int
    total: int


# --------------------------------------------------------------------------- #
#  Messages
# --------------------------------------------------------------------------- #
class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    role: str  # user | assistant | system
    content: str
    created_at: datetime


# --------------------------------------------------------------------------- #
#  Chats
# --------------------------------------------------------------------------- #
class ChatListItem(BaseModel):
    """Lightweight item for the chat list (no messages)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    profession_id: int | None = None
    created_at: datetime
    updated_at: datetime


class ChatDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    profession_id: int | None = None
    created_at: datetime
    updated_at: datetime
    messages: list[MessageOut] = []


class ChatCreate(BaseModel):
    """Create a chat. Both fields are optional: a chat can be free or bound to a
    profession (the "profession details" context). When `title` is omitted it is
    derived from the bound profession's label, or defaults to "New chat"."""

    title: str | None = Field(default=None, max_length=255)
    profession_id: int | None = None


class SendMessageRequest(BaseModel):
    content: str = Field(min_length=1, max_length=8000)


class SendMessageResponse(BaseModel):
    """Both messages that the turn produced (the saved user message and the
    generated assistant reply)."""

    user_message: MessageOut
    assistant_message: MessageOut
