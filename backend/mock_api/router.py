"""Contract-compatible Mock API routes."""

from __future__ import annotations

import asyncio
import logging
from typing import Annotated, Literal

from fastapi import APIRouter, Query, Response
from fastapi.responses import StreamingResponse

from api.errors import ERROR_RESPONSES, BizError
from api.schemas import (
    AskRequest,
    Conversation,
    ConversationCreate,
    ConversationUpdate,
    HealthStatus,
    Message,
    Page,
    StreamEvent,
)
from mock_api.store import MockStore
from mock_api.streaming import encode_line, stream_events

logger = logging.getLogger(__name__)
router = APIRouter()
store = MockStore()

STREAM_HEADERS = {
    "X-Accel-Buffering": "no",
    "Cache-Control": "no-cache",
}
STREAM_RESPONSES = {
    200: {
        "model": StreamEvent,
        "content": {"application/x-ndjson": {}},
        "description": "NDJSON 事件流，每行一个 JSON 对象。",
    },
    **ERROR_RESPONSES,
}


def _stream_response(payload: AskRequest, agent_type: Literal["rag", "graph"]):
    question = payload.question.strip()
    if not question:
        raise BizError(40001, "问题不能为空", "question 去除空白后长度为 0")

    is_new = payload.conversation_id is None
    if is_new:
        conversation = store.create_conversation(agent_type=agent_type)
        conversation_id = conversation.id
    else:
        conversation_id = payload.conversation_id
        conversation = store.get_conversation(conversation_id)
        if conversation is None:
            raise BizError(
                40401,
                "会话不存在",
                f"conversation_id={conversation_id} 在 Mock 内存存储中未找到",
            )

    async def event_stream():
        answer_parts: list[str] = []
        sources: list[dict] = []
        usage: dict | None = None
        try:
            async for event in stream_events(
                question=question,
                conversation_id=conversation_id,
                agent_type=agent_type,
                is_new=is_new,
            ):
                if "c" in event:
                    answer_parts.append(event["c"])
                elif "s" in event:
                    sources = event["s"]
                elif "u" in event:
                    usage = event["u"]
                yield encode_line(event)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.exception("Mock 问答流中断：%s", conversation_id)
            yield encode_line({"err": f"MockStreamError: {exc}"})
        finally:
            try:
                store.save_turn(conversation_id, question, "".join(answer_parts), sources, usage)
            except Exception:
                logger.exception("Mock 会话保存失败：%s", conversation_id)

    return StreamingResponse(
        event_stream(),
        media_type="application/x-ndjson; charset=utf-8",
        headers=STREAM_HEADERS,
    )


@router.post(
    "/ask",
    summary="Agentic RAG 对话（Mock 流式）",
    response_class=StreamingResponse,
    responses=STREAM_RESPONSES,
)
async def ask(payload: AskRequest):
    return _stream_response(payload, "rag")


@router.post(
    "/ask_graph",
    summary="医疗疾病问答（Mock 流式）",
    response_class=StreamingResponse,
    responses=STREAM_RESPONSES,
)
async def ask_graph(payload: AskRequest):
    return _stream_response(payload, "graph")


@router.get(
    "/conversations",
    response_model=Page[Conversation],
    responses=ERROR_RESPONSES,
    summary="会话列表",
)
def list_conversations(
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
):
    total, items = store.list_conversations(page=page, size=size)
    return Page[Conversation](total=total, page=page, size=size, items=items)


@router.post(
    "/conversations",
    response_model=Conversation,
    status_code=201,
    responses=ERROR_RESPONSES,
    summary="新建会话",
)
def create_conversation(payload: ConversationCreate):
    return store.create_conversation(title=payload.title, agent_type=payload.agent_type.value)


@router.patch(
    "/conversations/{conversation_id}",
    response_model=Conversation,
    responses=ERROR_RESPONSES,
    summary="重命名会话",
)
def rename_conversation(conversation_id: str, payload: ConversationUpdate):
    conversation = store.rename_conversation(conversation_id, payload.title)
    if conversation is None:
        raise BizError(40401, "会话不存在", f"conversation_id={conversation_id} 在 Mock 内存存储中未找到")
    return conversation


@router.delete(
    "/conversations/{conversation_id}",
    status_code=204,
    responses=ERROR_RESPONSES,
    summary="删除会话（级联删消息）",
)
def delete_conversation(conversation_id: str):
    if not store.delete_conversation(conversation_id):
        raise BizError(40401, "会话不存在", f"conversation_id={conversation_id} 在 Mock 内存存储中未找到")
    return Response(status_code=204)


@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=Page[Message],
    responses=ERROR_RESPONSES,
    summary="拉取历史消息",
)
def list_messages(
    conversation_id: str,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=200)] = 100,
):
    if store.get_conversation(conversation_id) is None:
        raise BizError(40401, "会话不存在", f"conversation_id={conversation_id} 在 Mock 内存存储中未找到")
    total, items = store.list_messages(conversation_id, page=page, size=size)
    return Page[Message](total=total, page=page, size=size, items=items)


@router.get(
    "/health",
    response_model=HealthStatus,
    summary="依赖健康检查",
)
def health() -> HealthStatus:
    return HealthStatus(
        mysql="mock",
        neo4j="mock",
        ollama="mock",
        faiss_index="mock",
        bm25_corpus="mock",
        rerank="mock",
    )
