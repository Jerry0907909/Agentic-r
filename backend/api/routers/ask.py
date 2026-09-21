"""接口层 · L1 问答域：`POST /api/ask` 与 `POST /api/ask_graph`。

两个端点请求体与响应格式完全一致，差别只在**绑定的智能体**：
    /api/ask        只给医学资料检索工具（rag_agent）
    /api/ask_graph  只给图谱工具、模型固定云端 Qwen（cypher_agent）

为什么不做成一个接口加参数：两者提示词、工具集、所用模型都不同，合成一个会让
「同一个 URL 的行为依赖参数分支」，前端无法从 URL 判断该期待什么能力，也不利于
分别监控（见 接口文档.md §3.3）。

流式协议见 接口文档.md §3.4 —— 事件顺序固定为：
    sid?  →  c  c  c  ...  c  →  s?  →  u?
"""

from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from agent import cypher_agent, rag_agent
from agent.runtime import MAX_CONTEXT_MESSAGES
from api.errors import ERROR_RESPONSES, BizError
from api.schemas import AskRequest, StreamEvent
from db.repository import ConversationRepository
from db.session import SessionLocal

logger = logging.getLogger(__name__)

router = APIRouter()

# 停止反向代理缓冲，否则流式会「攒够一批才转发」，打字机效果消失
STREAM_HEADERS = {
    "X-Accel-Buffering": "no",
    "Cache-Control": "no-cache",
}


def _line(obj: dict) -> str:
    """序列化一行 NDJSON。

    `ensure_ascii=False` 不能省：不加的话中文全部变成 \\uXXXX 转义，
    前端可读性差且体积膨胀（见 接口文档.md §1.1）。
    """
    return json.dumps(obj, ensure_ascii=False) + "\n"


# ── 与数据库交互的同步辅助函数 ──────────────────────────────────────────────
# 路由是 async 的，而 SQLAlchemy + PyMySQL 是同步驱动。这里统一用
# asyncio.to_thread 把它们挪到线程池，避免阻塞事件循环
# （见 系统设计.md §1.1 的代价与缓解措施）。
# 每次都在函数内部开新 Session，不复用请求级 Session —— 流式响应在路由返回
# 之后才真正执行，那时请求级 Session 已经关闭了。

def _create_conversation(agent_type: str, question: str) -> tuple[str, str]:
    """建会话，并直接用首条提问前 20 字作标题。返回 (会话ID, 标题)。"""
    db = SessionLocal()
    try:
        repo = ConversationRepository(db)
        title = question.strip().replace("\n", " ")[:20] or "新会话"
        conv = repo.create_conversation(title=title, agent_type=agent_type)
        return conv.id, conv.title
    finally:
        db.close()


def _conversation_exists(conversation_id: str) -> bool:
    db = SessionLocal()
    try:
        return ConversationRepository(db).get_conversation(conversation_id) is not None
    finally:
        db.close()


def _make_history_loader(conversation_id: str):
    """冷启动回灌用的历史读取器。

    做成**闭包 + 懒调用**而不是「先把历史读出来传给 agent」，是为了保住热路径
    的零数据库开销：同一会话连续提问时，checkpointer 里已有上下文，这个闭包
    根本不会被调用（见 系统设计.md §1.7.3）。
    """

    def load() -> list[dict]:
        db = SessionLocal()
        try:
            rows = ConversationRepository(db).get_recent_messages(
                conversation_id, MAX_CONTEXT_MESSAGES
            )
            # 只回灌 user / assistant 两类；工具调用过程不进上下文
            return [{"role": m.role, "content": m.content} for m in rows]
        finally:
            db.close()

    return load


def _persist(conversation_id: str, question: str, answer: str, sources, usage) -> None:
    db = SessionLocal()
    try:
        ConversationRepository(db).save_turn(
            conversation_id, question, answer, sources, usage
        )
    finally:
        db.close()


# ── 主逻辑 ──────────────────────────────────────────────────────────────────
async def _stream_ask(payload: AskRequest, agent_type: str, agent_module):
    question = (payload.question or "").strip()
    if not question:
        raise BizError(40001, "问题不能为空", "question 去除空白后长度为 0")

    is_new = payload.conversation_id is None
    if is_new:
        # 会话在**开始流式之前**建好：这样首行 sid 回传的就是真实存在的会话 ID，
        # 前端立刻就能用它拉历史、续聊；也保证后面写 message 时外键一定成立。
        conversation_id, _ = await asyncio.to_thread(
            _create_conversation, agent_type, question
        )
    else:
        conversation_id = payload.conversation_id
        # 校验必须在流开始前做 —— 一旦响应头发出去，就无法再改 HTTP 状态码了
        # （见 接口文档.md §3.2 的错误说明）。
        if not await asyncio.to_thread(_conversation_exists, conversation_id):
            raise BizError(
                40401,
                "会话不存在",
                f"conversation_id={conversation_id} 在 agentic_rag.conversation 中未找到",
            )

    async def event_stream():
        # ① 新建会话时先下发 sid（约定：sid 若出现，必定是第一行）
        if is_new:
            yield _line({"sid": conversation_id})

        answer_parts: list[str] = []
        sources: list[dict] = []
        usage: dict | None = None

        try:
            async for event in agent_module.stream_agent(
                question=question,
                conversation_id=conversation_id,
                use_memory=payload.use_memory,
                history_loader=_make_history_loader(conversation_id),
            ):
                if "c" in event:
                    answer_parts.append(event["c"])
                elif "s" in event:
                    sources = event["s"]
                elif "u" in event:
                    usage = event["u"]
                # 逐事件原样下发；s / u 由 agent 层保证在正文之后产出
                yield _line(event)
        except Exception as exc:
            # 流已开始，改不了状态码，只能下发 err 事件后终止
            logger.exception("问答流中断：%s", conversation_id)
            yield _line({"err": _describe_error(exc)})
        finally:
            # ② 落库：同一事务写 user + assistant 两条消息。
            #    放在 finally 里，是为了让「用户点了停止」这种中断场景也把提问存下来，
            #    否则用户会看到问题消失了。
            answer = "".join(answer_parts)
            try:
                await asyncio.to_thread(
                    _persist, conversation_id, question, answer, sources, usage
                )
            except asyncio.CancelledError:
                # 客户端 abort 后协程已被取消，上面的 await 会立刻抛 CancelledError，
                # 线程池那一步可能压根没跑。改用同步写补一次 —— 这条写只有
                # 两次 INSERT + 一次 UPDATE（本地库约 1-3ms），值得用这点阻塞
                # 换取「有提问必有回答」不落空。
                try:
                    _persist(conversation_id, question, answer, sources, usage)
                except Exception:
                    logger.exception("中止后补写落库失败：%s", conversation_id)
                raise
            except Exception:
                logger.exception("落库失败：%s", conversation_id)

    return StreamingResponse(
        event_stream(),
        # media_type 必须带 charset：否则部分客户端按 latin-1 解码，中文乱码
        media_type="application/x-ndjson; charset=utf-8",
        headers=STREAM_HEADERS,
    )


def _describe_error(exc: Exception) -> str:
    """把异常翻成用户能看懂、开发者能排查的一句话。

    保留真实异常类型与原文（见 接口文档.md §1.3）：只给「服务异常」四个字，
    演示现场出问题时只能靠猜。
    """
    text = f"{type(exc).__name__}: {exc}"
    lowered = text.lower()
    if "faiss" in lowered or "向量库" in text:
        return f"向量库不可用（请执行 python utils/rag_index.py medical 构建索引）。{text}"
    if "neo4j" in lowered or "auth" in lowered:
        return f"图谱服务不可用（请检查 Neo4j 实例是否已启动）。{text}"
    if "timeout" in lowered or "connection" in lowered:
        return f"模型服务不可用（网络超时或额度耗尽），可改用本地模型重试。{text}"
    return f"回答生成失败。{text}"


@router.post(
    "/ask",
    summary="医疗健康问答（流式）",
    response_class=StreamingResponse,
    responses={
        200: {
            # 声明 model 不是为了描述响应体（NDJSON 流描述不了），而是当**类型锚点**：
            # FastAPI 借此把 StreamEvent / Source / Usage 写进 components.schemas，
            # 前端 `npm run api:types` 才能生成出这几个类型（见 api/schemas.py 的说明）。
            # FastAPI 会因此额外补一个 application/json 条目，已在 chat_api.py 里后处理去掉。
            "model": StreamEvent,
            "content": {"application/x-ndjson": {}},
            "description": "NDJSON 事件流，每行一个 JSON 对象。"
                           "事件顺序固定为 sid? → c c c … c → s? → u?，详见《接口文档》§3.4",
        },
        # 流开始**之前**的失败走 HTTP 状态码 + 错误信封；
        # 流开始之后的失败改走 `err` 事件（响应头已发出，改不了状态码）
        **ERROR_RESPONSES,
    },
)
async def ask(payload: AskRequest):
    """医学资料智能体：仅使用文档检索，不调用知识图谱。"""
    return await _stream_ask(payload, "rag", rag_agent)


@router.post(
    "/ask_graph",
    summary="医疗疾病问答（流式）",
    response_class=StreamingResponse,
    responses={
        200: {
            # 声明 model 不是为了描述响应体（NDJSON 流描述不了），而是当**类型锚点**：
            # FastAPI 借此把 StreamEvent / Source / Usage 写进 components.schemas，
            # 前端 `npm run api:types` 才能生成出这几个类型（见 api/schemas.py 的说明）。
            # FastAPI 会因此额外补一个 application/json 条目，已在 chat_api.py 里后处理去掉。
            "model": StreamEvent,
            "content": {"application/x-ndjson": {}},
            "description": "NDJSON 事件流，每行一个 JSON 对象。"
                           "事件顺序固定为 sid? → c c c … c → s? → u?，详见《接口文档》§3.4",
        },
        # 流开始**之前**的失败走 HTTP 状态码 + 错误信封；
        # 流开始之后的失败改走 `err` 事件（响应头已发出，改不了状态码）
        **ERROR_RESPONSES,
    },
)
async def ask_graph(payload: AskRequest):
    """单图谱工具智能体：只查 Neo4j 医疗知识图谱。"""
    return await _stream_ask(payload, "graph", cypher_agent)
