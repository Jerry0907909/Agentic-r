"""数据层：SQLAlchemy 2.0 ORM 模型。

与 db/schema.sql 的 DDL 一一对应，改表结构时两边同步改。

写法说明：全部使用 SQLAlchemy 2.0 的 `Mapped[...]` + `mapped_column(...)`
声明式风格（取代 1.x 的 `Column(...)`）。好处是类型注解即列类型，
IDE 与 mypy 能直接推断属性类型，不再需要 `# type: ignore`。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CHAR,
    ForeignKeyConstraint,
    Index,
    Integer,
    JSON,
    String,
    text,
)
from sqlalchemy.dialects.mysql import DATETIME as MYSQL_DATETIME
from sqlalchemy.dialects.mysql import MEDIUMTEXT
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# ── 时间戳列的统一定义 ──────────────────────────────────────────────────────
# 两个坑，都踩过：
#
# 1. `server_onupdate=func.current_timestamp()` **不会**生成
#    `ON UPDATE CURRENT_TIMESTAMP`。SQLAlchemy 的 server_onupdate 只是给 ORM
#    的一个提示（用于 commit 后刷新属性），它不参与 DDL 渲染。实测 SHOW CREATE
#    TABLE 出来的 updated_at 光秃秃一个 DEFAULT，于是「追加消息 → 会话按最近更新
#    倒序」永远不生效：updated_at 停在创建那一刻，会话列表顺序再也不变。
#    正确做法是把整段子句塞进 server_default —— SQLAlchemy 会把它原样渲染。
#
# 2. 必须用 mysql 方言的 DATETIME(fsp=3) 才能得到 DATETIME(3)。用通用的
#    DateTime 生成的是 DATETIME（秒精度），与 系统设计.md §3.2 的 DDL 不符；
#    毫秒精度对「同一秒内多条消息按 created_at 排序」是必要的。
CREATED_AT = MYSQL_DATETIME(fsp=3)
NOW_3 = text("CURRENT_TIMESTAMP(3)")
NOW_3_ON_UPDATE = text("CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3)")


class Base(DeclarativeBase):
    """全项目 ORM 基类。"""


class Conversation(Base):
    """会话。主键是 UUID 字符串，不是自增整数（见 schema.sql 的注释）。"""

    __tablename__ = "conversation"

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, comment="会话ID（UUID v4）")
    title: Mapped[str] = mapped_column(
        String(120), nullable=False, default="新会话", server_default="新会话"
    )
    agent_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="rag", server_default="rag"
    )
    # message_count / total_tokens 是冗余字段，可由 message 表聚合得出。
    # 冗余的目的是让会话列表页免于每页跑 20 次聚合子查询（见 系统设计.md §3.3）。
    message_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        CREATED_AT, nullable=False, server_default=NOW_3
    )
    # updated_at 交给 MySQL 的 ON UPDATE CURRENT_TIMESTAMP(3) 自动维护：
    # 只要该行有任何字段被 UPDATE，时间戳就会刷新。这样「追加一条消息 →
    # 会话按最近更新倒序」是数据库层面的必然行为，不依赖应用层记得去改它。
    updated_at: Mapped[datetime] = mapped_column(
        CREATED_AT, nullable=False, server_default=NOW_3_ON_UPDATE
    )

    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:  # pragma: no cover - 仅调试用
        return f"<Conversation {self.id} {self.title!r}>"


class Message(Base):
    """消息。user 角色的 sources 与全部 token 字段均为 NULL。"""

    __tablename__ = "message"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    conversation_id: Mapped[str] = mapped_column(CHAR(36), nullable=False)
    role: Mapped[str] = mapped_column(String(10), nullable=False, comment="user | assistant")
    # MEDIUMTEXT（16MB）而非 TEXT（64KB）：一条长回答带 Markdown 表格很容易超过 64KB
    content: Mapped[str] = mapped_column(MEDIUMTEXT, nullable=False)
    # JSON 列：SQLAlchemy 的 JSON 类型原生支持 dict/list 的自动序列化与反序列化
    sources: Mapped[list | None] = mapped_column(JSON, nullable=True)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        CREATED_AT, nullable=False, server_default=NOW_3
    )

    conversation: Mapped[Conversation] = relationship(back_populates="messages")

    __table_args__ = (
        # 外键用显式的 ForeignKeyConstraint 而不是列上的 ForeignKey(...)：
        # 后者由 SQLAlchemy 自动命名（实测生成 message_ibfk_1），
        # 与 schema.sql / 系统设计.md 里约定的 fk_message_conversation 对不上，
        # 排查问题时按文档里的名字去 DROP FOREIGN KEY 会直接报「不存在」。
        ForeignKeyConstraint(
            ["conversation_id"],
            ["conversation.id"],
            name="fk_message_conversation",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        # 拉取历史消息是 WHERE conversation_id = ? ORDER BY created_at，该联合索引同时覆盖过滤与排序
        Index("idx_conv_created", "conversation_id", "created_at"),
    )

    def __repr__(self) -> str:  # pragma: no cover - 仅调试用
        return f"<Message {self.id} {self.role}>"


class RetrievalLog(Base):
    """检索可观测日志（可选扩展表）。

    表结构已按 系统设计.md §3.2 建好，但**当前代码尚未写入** —— 它属于
    MoSCoW 的「可以有」档，保留结构是为了后续做「混合检索 vs 纯向量」
    召回对比评测时能直接落数据，不必再改表。
    """

    __tablename__ = "retrieval_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    message_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    channel: Mapped[str] = mapped_column(String(16), nullable=False, comment="dense | sparse | rerank")
    query: Mapped[str] = mapped_column(String(512), nullable=False)
    hit_count: Mapped[int] = mapped_column(Integer, nullable=False)
    elapsed_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    rerank_enabled: Mapped[bool] = mapped_column(nullable=False, default=True, server_default="1")
    created_at: Mapped[datetime] = mapped_column(
        CREATED_AT, nullable=False, server_default=NOW_3
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["message_id"],
            ["message.id"],
            name="fk_log_message",
            ondelete="CASCADE",
        ),
        Index("idx_message", "message_id"),
    )


# ── 表级索引 ────────────────────────────────────────────────────────────────
# 降序索引只能在这里声明，不能写进 Conversation 类体的 __table_args__：
# 类体里的 `updated_at` 是 mapped_column() 返回的 MappedColumn，不提供 .desc()；
# 而 Table.c.updated_at 是真正的 Column，.desc() 才能生成 DESC 排序表达式。
# 会话列表固定按 updated_at DESC，降序索引可完全避免 filesort（见 系统设计.md §3.3）。
Index("idx_updated_at", Conversation.__table__.c.updated_at.desc())
