"""接口层：全部 Pydantic v2 模型。

严格对齐 接口文档.md §6.2 的定义 —— 这份 schema 是前端类型的来源
（前端跑 `npm run api:types` 从 /openapi.json 自动生成，不手写），
所以字段名、类型、可空性都不能随意改。
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Annotated, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_serializer

# 数据库里存的是 naive datetime（MySQL DATETIME 不带时区），
# 而接口文档 §1.1 要求输出 ISO 8601 **带时区**（如 2026-09-19T15:02:11+08:00）。
# 这里按运行机器的本地时区补上偏移量。
LOCAL_TZ = datetime.now().astimezone().tzinfo


def _isoformat(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=LOCAL_TZ)
    return dt.isoformat()


# ── 枚举 ────────────────────────────────────────────────────────────────────
class AgentType(str, Enum):
    RAG = "rag"        # 单医学资料检索智能体
    GRAPH = "graph"    # 单图谱工具智能体


class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"


# ── 请求体 ──────────────────────────────────────────────────────────────────
class AskRequest(BaseModel):
    """问答请求。前端两个 Tab 共用此结构。"""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "question": "百日咳有哪些症状",
                "conversation_id": None,
                "use_memory": True,
            }
        }
    )

    question: Annotated[str, Field(min_length=1, max_length=2000, description="用户问题")]
    conversation_id: Annotated[
        str | None, Field(default=None, description="会话 ID，传 null 表示新建")
    ]
    use_memory: Annotated[bool, Field(default=True, description="是否携带历史上下文")]


class ConversationCreate(BaseModel):
    title: Annotated[str, Field(default="新会话", max_length=120)]
    agent_type: Annotated[AgentType, Field(default=AgentType.RAG)]


class ConversationUpdate(BaseModel):
    title: Annotated[str, Field(min_length=1, max_length=120)]


# ── 响应模型 ────────────────────────────────────────────────────────────────
class Source(BaseModel):
    """回答的溯源来源。对应 系统设计.md §1.6 与 接口文档.md §3.4.5。"""

    type: Literal["vector", "graph"]
    name: str
    score: float | None = Field(default=None, description="图谱类固定为 null")
    snippet: str
    meta: dict | None = None


class Usage(BaseModel):
    """token 用量。本地 Ollama 模型可能不产生该数据。"""

    prompt: int
    completion: int
    total: int
    model: str
    latency_ms: int


class Conversation(BaseModel):
    """会话。由 SQLAlchemy ORM 对象直接构造。"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    agent_type: AgentType
    message_count: int
    total_tokens: int
    created_at: datetime
    updated_at: datetime

    @field_serializer("created_at", "updated_at")
    def _ser_dt(self, dt: datetime) -> str:
        return _isoformat(dt)


class Message(BaseModel):
    """消息。user 角色的 sources 与 token 字段均为 null。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    role: MessageRole
    content: str
    sources: list[Source] | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    model: str | None = None
    latency_ms: int | None = None
    created_at: datetime

    @field_serializer("created_at")
    def _ser_dt(self, dt: datetime) -> str:
        return _isoformat(dt)


T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    """通用分页信封。Pydantic v2 原生支持泛型模型（v1 需要 GenericModel）。"""

    total: int
    page: int
    size: int
    items: list[T]


class ErrorBody(BaseModel):
    """统一错误信封。`detail` 必须携带真实异常类型与原文（见 接口文档.md §1.3）。"""

    code: int
    msg: str
    detail: str | None = None


class HealthStatus(BaseModel):
    """健康检查。**始终返回 200**，靠字段值判断哪个依赖挂了。"""

    mysql: str
    neo4j: str
    ollama: str
    faiss_index: str
    bm25_corpus: str
    rerank: str


class StreamEvent(BaseModel):
    """流式响应中**一行** NDJSON 的载荷（见 接口文档.md §3.4.2）。

    OpenAPI 描述不了「一行一个 JSON、连接关闭即结束」这种协议，所以这个模型
    并不是真正的 response_model —— 它的作用是当**类型锚点**：
    把它挂到 /api/ask 的 responses 里，`Usage` 与 `Source` 才会被写进
    components.schemas，前端 `npm run api:types` 生成出来的类型里才有它们。

    接口文档 §6.3 的手写 `StreamEvent` 联合类型（`{sid} | {c} | {s} | {u} | {err}`）
    仍然需要手写 —— 联合类型的判别信息在这份 schema 里表达不出来。
    但至少 Source / Usage 这两个**嵌套结构**不必再手抄一遍，字段改了也不会漏。
    """

    sid: str | None = Field(default=None, description="新建会话时首行下发真实会话 ID")
    c: str | None = Field(default=None, description="正文增量")
    s: list[Source] | None = Field(default=None, description="溯源来源")
    u: Usage | None = Field(default=None, description="token 用量")
    err: str | None = Field(default=None, description="错误描述，收到后流终止")
