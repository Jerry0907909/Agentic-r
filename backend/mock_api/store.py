"""Thread-safe process-local conversation store for the Mock API."""

from __future__ import annotations

from datetime import datetime, timedelta
from itertools import count
from threading import RLock
from typing import TypeVar
from uuid import uuid4

from api.schemas import AgentType, Conversation, Message, MessageRole

T = TypeVar("T")
DEFAULT_TITLE = "新会话"
TITLE_MAX_CHARS = 20


def _now() -> datetime:
    return datetime.now().astimezone()


def _page(items: list[T], page: int, size: int) -> list[T]:
    start = (page - 1) * size
    return items[start:start + size]


class MockStore:
    """In-memory implementation of the conversation repository contract."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._conversations: dict[str, Conversation] = {}
        self._messages: dict[str, list[Message]] = {}
        self._message_ids = count(1)
        self._last_timestamp: datetime | None = None

    def _next_timestamp(self) -> datetime:
        current = _now()
        if self._last_timestamp is not None and current <= self._last_timestamp:
            current = self._last_timestamp + timedelta(microseconds=1)
        self._last_timestamp = current
        return current

    def reset(self) -> None:
        with self._lock:
            self._conversations.clear()
            self._messages.clear()
            self._message_ids = count(1)
            self._last_timestamp = None

    def create_conversation(
        self,
        title: str = DEFAULT_TITLE,
        agent_type: str = AgentType.RAG.value,
        conversation_id: str | None = None,
    ) -> Conversation:
        with self._lock:
            now = self._next_timestamp()
            conversation = Conversation(
                id=conversation_id or str(uuid4()),
                title=title or DEFAULT_TITLE,
                agent_type=AgentType(agent_type),
                message_count=0,
                total_tokens=0,
                created_at=now,
                updated_at=now,
            )
            self._conversations[conversation.id] = conversation
            self._messages[conversation.id] = []
            return conversation.model_copy(deep=True)

    def get_conversation(self, conversation_id: str) -> Conversation | None:
        with self._lock:
            conversation = self._conversations.get(conversation_id)
            return conversation.model_copy(deep=True) if conversation else None

    def list_conversations(self, page: int = 1, size: int = 20) -> tuple[int, list[Conversation]]:
        with self._lock:
            items = sorted(
                self._conversations.values(),
                key=lambda conversation: conversation.updated_at,
                reverse=True,
            )
            return len(items), [item.model_copy(deep=True) for item in _page(items, page, size)]

    def rename_conversation(self, conversation_id: str, title: str) -> Conversation | None:
        with self._lock:
            conversation = self._conversations.get(conversation_id)
            if conversation is None:
                return None
            conversation.title = title
            conversation.updated_at = self._next_timestamp()
            return conversation.model_copy(deep=True)

    def delete_conversation(self, conversation_id: str) -> bool:
        with self._lock:
            if conversation_id not in self._conversations:
                return False
            del self._conversations[conversation_id]
            del self._messages[conversation_id]
            return True

    def list_messages(
        self, conversation_id: str, page: int = 1, size: int = 100
    ) -> tuple[int, list[Message]]:
        with self._lock:
            if conversation_id not in self._conversations:
                raise LookupError(f"会话不存在：{conversation_id}")
            messages = self._messages[conversation_id]
            return len(messages), [item.model_copy(deep=True) for item in _page(messages, page, size)]

    def get_recent_messages(self, conversation_id: str, limit: int) -> list[Message]:
        with self._lock:
            if conversation_id not in self._conversations:
                raise LookupError(f"会话不存在：{conversation_id}")
            return [item.model_copy(deep=True) for item in self._messages[conversation_id][-limit:]]

    def save_turn(
        self,
        conversation_id: str,
        question: str,
        answer: str,
        sources: list[dict] | None,
        usage: dict | None,
    ) -> tuple[Message, Message]:
        with self._lock:
            conversation = self._conversations.get(conversation_id)
            if conversation is None:
                raise LookupError(f"会话不存在：{conversation_id}")

            now = self._next_timestamp()
            is_first_turn = conversation.message_count == 0
            user_message = Message(
                id=next(self._message_ids),
                role=MessageRole.USER,
                content=question,
                sources=None,
                created_at=now,
            )
            usage = usage or {}
            assistant_message = Message(
                id=next(self._message_ids),
                role=MessageRole.ASSISTANT,
                content=answer,
                sources=sources or None,
                prompt_tokens=usage.get("prompt"),
                completion_tokens=usage.get("completion"),
                total_tokens=usage.get("total"),
                model=usage.get("model"),
                latency_ms=usage.get("latency_ms"),
                created_at=self._next_timestamp(),
            )
            self._messages[conversation_id].extend([user_message, assistant_message])
            conversation.message_count += 2
            conversation.total_tokens += int(usage.get("total") or 0)
            conversation.updated_at = self._next_timestamp()
            if is_first_turn and conversation.title in (DEFAULT_TITLE, ""):
                title = question.strip().replace("\n", " ")
                conversation.title = title[:TITLE_MAX_CHARS] or DEFAULT_TITLE

            return user_message.model_copy(deep=True), assistant_message.model_copy(deep=True)
