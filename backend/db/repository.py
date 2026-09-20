"""数据层：会话与消息的数据访问封装。

对应 系统设计.md §3.4。接口层只调这里的方法，**不写裸 SQL** ——
这样「一次问答两次写入必须同事务」「冗余计数怎么维护」这类规则只有一处实现，
不会在多个路由里各写一遍、各漏一点。
"""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from db.models import Conversation, Message

# 新建会话的默认标题。save_turn 见到这个值就说明还没被首条提问覆盖过。
DEFAULT_TITLE = "新会话"

# 标题取自首条提问的字符数（见 需求分析.md F7）
TITLE_MAX_CHARS = 20


class ConversationRepository:
    """会话与消息的 CRUD。

    实例持有一个 Session，生命周期由调用方（依赖注入）管理。
    """

    def __init__(self, session: Session):
        self.session = session

    # ── 内部工具 ────────────────────────────────────────────────────────
    def _flush_refresh(self, obj):
        """flush 后立刻把服务端生成的列值读回来。

        为什么必须做：`created_at` / `updated_at` 用的是 MySQL 的
        DEFAULT CURRENT_TIMESTAMP(3) 与 ON UPDATE CURRENT_TIMESTAMP(3)，
        这些值由**数据库**生成，Python 侧的 ORM 对象并不知道。
        再加上引擎配了 expire_on_commit=False（commit 后不过期属性），
        不 refresh 的话返回给接口层的对象里这两个字段就是 None，
        Pydantic 序列化时直接报「created_at 字段缺失」。
        """
        self.session.flush()
        self.session.refresh(obj)
        return obj

    # ── 会话 ────────────────────────────────────────────────────────────
    def create_conversation(
        self,
        title: str = DEFAULT_TITLE,
        agent_type: str = "rag",
        conversation_id: str | None = None,
    ) -> Conversation:
        """新建会话。conversation_id 缺省时服务端生成 UUID v4。

        会话 ID 由**服务端**生成（见 需求分析.md F2）：前端传 null 表示新建，
        服务端建好后通过流的首行 `sid` 事件回传，前端记录后用于后续请求。
        """
        conv = Conversation(
            id=conversation_id or str(uuid4()),
            title=title or DEFAULT_TITLE,
            agent_type=agent_type,
            message_count=0,
            total_tokens=0,
        )
        self.session.add(conv)
        self._flush_refresh(conv)
        self.session.commit()
        return conv

    def get_conversation(self, conversation_id: str) -> Conversation | None:
        """按 ID 取会话。

        populate_existing=True 不能省：SQLAlchemy 的 Session 有 identity map，
        查询若命中已加载过的对象会**直接返回内存里的旧属性**，不覆盖。
        而 `updated_at` 是 MySQL 的 ON UPDATE 在服务端改的，应用层无从得知 ——
        不强制刷新的话，同一个 Session 里连续「写一轮问答 → 读会话」会读到
        上一轮的 updated_at 和 message_count，表现为「列表排序/计数偶发不更新」。
        本项目的接口层是每请求一个 Session，影响有限；但规则定在这里，
        免得将来有人复用 Session 时踩坑。
        """
        return self.session.get(Conversation, conversation_id, populate_existing=True)

    def list_conversations(self, page: int = 1, size: int = 20) -> tuple[int, list[Conversation]]:
        """会话列表，按最近更新倒序。返回 (总条数, 当前页)。"""
        total = self.session.scalar(select(func.count()).select_from(Conversation)) or 0
        items = list(
            self.session.scalars(
                select(Conversation)
                # 同 get_conversation：以库里的值为准，不用 identity map 的缓存副本
                .execution_options(populate_existing=True)
                # 降序索引 idx_updated_at 让这里完全避免 filesort
                .order_by(Conversation.updated_at.desc())
                .offset((page - 1) * size)
                .limit(size)
            ).all()
        )
        return total, items

    def rename_conversation(self, conversation_id: str, title: str) -> Conversation | None:
        conv = self.session.get(Conversation, conversation_id)
        if conv is None:
            return None
        conv.title = title
        self._flush_refresh(conv)
        self.session.commit()
        return conv

    def delete_conversation(self, conversation_id: str) -> bool:
        """删除会话。消息由外键 ON DELETE CASCADE 在数据库层级联删除。

        用批量 DELETE 而不是 `session.delete(obj)`：后者会先把 messages 关系
        加载进内存再逐条删，对一条长会话来说是几十次往返；而级联本来就是
        数据库保证的，没必要在应用层重做一遍。
        """
        result = self.session.execute(
            delete(Conversation).where(Conversation.id == conversation_id)
        )
        self.session.commit()
        return (result.rowcount or 0) > 0

    # ── 消息 ────────────────────────────────────────────────────────────
    def get_messages(
        self, conversation_id: str, page: int = 1, size: int = 100
    ) -> tuple[int, list[Message]]:
        """按时间正序拉取历史消息（对话顺序）。返回 (总条数, 当前页)。"""
        total = (
            self.session.scalar(
                select(func.count())
                .select_from(Message)
                .where(Message.conversation_id == conversation_id)
            )
            or 0
        )
        items = list(
            self.session.scalars(
                select(Message)
                .where(Message.conversation_id == conversation_id)
                # 二级排序键 id 不能省：created_at 是毫秒精度，同一轮问答的
                # user / assistant 两条消息可能落在同一毫秒，只按时间排序时
                # 顺序由存储引擎决定，会出现「回答排在提问前面」。
                .order_by(Message.created_at.asc(), Message.id.asc())
                .offset((page - 1) * size)
                .limit(size)
            ).all()
        )
        return total, items

    def get_recent_messages(self, conversation_id: str, limit: int) -> list[Message]:
        """取最近 limit 条消息，**按时间正序**返回。

        用于冷启动回灌（见 系统设计.md §1.7.4）。注意是「最近的 N 条」而不是
        「前 N 条」：会话很长时要保留的是尾部上下文，不是开头的问候语。
        实现上是先按倒序取 N 条再反转，保证返回顺序符合对话时序。
        """
        rows = list(
            self.session.scalars(
                select(Message)
                .where(Message.conversation_id == conversation_id)
                .order_by(Message.created_at.desc(), Message.id.desc())
                .limit(limit)
            ).all()
        )
        rows.reverse()
        return rows

    def save_turn(
        self,
        conversation_id: str,
        question: str,
        answer: str,
        sources: list[dict] | None = None,
        usage: dict | None = None,
    ) -> tuple[Message, Message]:
        """一次问答的两次写入：user 消息 + assistant 消息，**同一事务**。

        为什么必须同事务（见 系统设计.md §3.4）：分开提交时，若 assistant
        那次写入失败（模型报错、连接断开），库里就留下一个「有提问没回答」的
        残缺会话，用户回看时看到一个悬空的问题，且没有任何线索说明当时发生了什么。

        同时维护 conversation 的两个冗余字段：
            message_count += 2
            total_tokens  += usage.total
        以及首轮自动定标题。
        """
        conv = self.session.get(Conversation, conversation_id)
        if conv is None:
            raise LookupError(f"会话不存在：{conversation_id}")

        is_first_turn = (conv.message_count or 0) == 0

        user_msg = Message(
            conversation_id=conversation_id,
            role="user",
            content=question,
            # user 角色的 sources 与 token 字段保持 NULL：提问本身不消耗生成 token
            sources=None,
        )
        self.session.add(user_msg)

        usage = usage or {}
        assistant_msg = Message(
            conversation_id=conversation_id,
            role="assistant",
            content=answer,
            sources=sources or None,
            prompt_tokens=usage.get("prompt"),
            completion_tokens=usage.get("completion"),
            total_tokens=usage.get("total"),
            model=usage.get("model"),
            latency_ms=usage.get("latency_ms"),
        )
        self.session.add(assistant_msg)

        # 冗余计数：读多写少场景下用写入成本换列表页的查询成本（见 系统设计.md §3.3）
        conv.message_count = (conv.message_count or 0) + 2
        conv.total_tokens = (conv.total_tokens or 0) + int(usage.get("total") or 0)

        # 首轮用提问前 20 字作标题。放在 save_turn 里而不是建会话时，
        # 是因为「会话由 POST /api/ask 隐式创建」这条主路径上，
        # 建会话那一刻还不知道用户要问什么。
        if is_first_turn and conv.title in (DEFAULT_TITLE, "", None):
            title = question.strip().replace("\n", " ")
            conv.title = title[:TITLE_MAX_CHARS] or DEFAULT_TITLE

        self.session.flush()
        self.session.commit()
        # 两条消息的 created_at 由数据库生成，刷新后才有值；
        # conv 也必须刷新 —— 我们刚改过它的 message_count / total_tokens / title，
        # 而 updated_at 更是 MySQL 的 ON UPDATE 在服务端改的，内存对象并不知情。
        self.session.refresh(user_msg)
        self.session.refresh(assistant_msg)
        self.session.refresh(conv)
        return user_msg, assistant_msg

    # ── 统计（供 /api/health 与排障用）──────────────────────────────────
    def count_messages(self, conversation_id: str) -> int:
        return (
            self.session.scalar(
                select(func.count())
                .select_from(Message)
                .where(Message.conversation_id == conversation_id)
            )
            or 0
        )
