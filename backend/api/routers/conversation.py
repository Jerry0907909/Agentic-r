"""接口层 · L2 会话域：会话列表 / 新建 / 重命名 / 删除 / 历史消息。

对应 需求分析.md F7 与 接口文档.md §4。

**这些路由写成同步 `def` 而不是 `async def`**：SQLAlchemy + PyMySQL 是同步驱动，
FastAPI 对同步路由会自动放到线程池执行，不会阻塞事件循环；写成 `async def`
反而会让数据库调用直接占住事件循环。问答域那两个是流式接口，必须 async，
所以它们内部用 asyncio.to_thread 把数据库操作挪走（见 api/routers/ask.py）。
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query, Response

from agent import cypher_agent, rag_agent
from api.deps import RepoDep
from api.errors import ERROR_RESPONSES, BizError
from api.schemas import Conversation, ConversationCreate, ConversationUpdate, Message, Page

router = APIRouter()


@router.get(
    "/conversations",
    response_model=Page[Conversation],
    responses=ERROR_RESPONSES,
    summary="会话列表",
    description="按最近更新时间倒序返回会话，用于左侧边栏。",
)
def list_conversations(
    repo: RepoDep,
    page: Annotated[int, Query(ge=1, description="页码，从 1 开始")] = 1,
    size: Annotated[int, Query(ge=1, le=100, description="每页条数")] = 20,
):
    total, items = repo.list_conversations(page=page, size=size)
    return Page[Conversation](
        total=total,
        page=page,
        size=size,
        items=[Conversation.model_validate(c) for c in items],
    )


@router.post(
    "/conversations",
    response_model=Conversation,
    status_code=201,
    responses=ERROR_RESPONSES,
    summary="新建会话",
    description="主要用于「点新建按钮时先建一个空会话占位」。"
                "走 POST /api/ask 且 conversation_id 传 null 时会自动建会话，无需先调本接口。",
)
def create_conversation(payload: ConversationCreate, repo: RepoDep):
    conv = repo.create_conversation(title=payload.title, agent_type=payload.agent_type.value)
    return Conversation.model_validate(conv)


@router.patch(
    "/conversations/{conversation_id}",
    response_model=Conversation,
    responses=ERROR_RESPONSES,
    summary="重命名会话",
    description="用 PATCH 而非 PUT：会话还有 agent_type、message_count 等字段，"
                "PUT 的「整体替换」语义要求客户端提交完整对象，而这里只改标题。",
)
def rename_conversation(conversation_id: str, payload: ConversationUpdate, repo: RepoDep):
    conv = repo.rename_conversation(conversation_id, payload.title)
    if conv is None:
        raise BizError(
            40401, "会话不存在", f"conversation_id={conversation_id} 在 agentic_rag.conversation 中未找到"
        )
    return Conversation.model_validate(conv)


@router.delete(
    "/conversations/{conversation_id}",
    status_code=204,
    responses=ERROR_RESPONSES,
    summary="删除会话（级联删消息）",
    description="消息由数据库外键 ON DELETE CASCADE 自动删除，前端不需要先删消息。",
)
def delete_conversation(conversation_id: str, repo: RepoDep):
    if not repo.delete_conversation(conversation_id):
        raise BizError(
            40401, "会话不存在", f"conversation_id={conversation_id} 在 agentic_rag.conversation 中未找到"
        )

    # 同步清理两个智能体在内存中的对话上下文。
    # 不做这一步，被删会话的上下文会变成幽灵数据长期占用内存
    # （见 系统设计.md §1.7.7）。清理失败不影响删除结果，agent 层内部已吞异常并记日志。
    for agent in (rag_agent, cypher_agent):
        agent.delete_thread(conversation_id)

    # 204 不能带响应体（接口文档.md §4.5 明确提醒前端不要调 res.json()）
    return Response(status_code=204)


@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=Page[Message],
    responses=ERROR_RESPONSES,
    summary="拉取历史消息",
    description="按 created_at 正序（对话顺序）返回。user 角色的 sources 与 token 字段均为 null。",
)
def list_messages(
    conversation_id: str,
    repo: RepoDep,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=200)] = 100,
):
    # 先确认会话存在：否则「会话被删了但前端还在拉消息」会返回空列表，
    # 前端无从区分「会话为空」和「会话不存在」，也就不知道该不该把本地会话项移除。
    if repo.get_conversation(conversation_id) is None:
        raise BizError(
            40401, "会话不存在", f"conversation_id={conversation_id} 在 agentic_rag.conversation 中未找到"
        )

    total, items = repo.get_messages(conversation_id, page=page, size=size)
    return Page[Message](
        total=total,
        page=page,
        size=size,
        items=[Message.model_validate(m) for m in items],
    )
