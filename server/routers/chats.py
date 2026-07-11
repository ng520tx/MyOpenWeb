from __future__ import annotations

from fastapi import APIRouter, Response, status

from server.repositories.chats import delete_chat, list_chats, upsert_chat
from server.schemas.chat import Conversation, ConversationsResponse

router = APIRouter(prefix="/api/chats", tags=["chats"])


@router.get("", response_model=ConversationsResponse)
def get_chats() -> ConversationsResponse:
    return ConversationsResponse(conversations=list_chats())


@router.put("/{chat_id}", response_model=Conversation)
def put_chat(chat_id: str, conversation: Conversation) -> Conversation:
    if conversation.id != chat_id:
        conversation = conversation.model_copy(update={"id": chat_id})
    return upsert_chat(conversation)


@router.delete("/{chat_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_chat(chat_id: str) -> Response:
    delete_chat(chat_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
