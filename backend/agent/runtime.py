"""智能体层 · 公共运行时：状态定义、图装配、流式事件产出。

`rag_agent` 与 `cypher_agent` 只差三样东西 —— 提示词、工具集、模型。
其余（记忆、溯源收集、用量统计、上下文裁剪、冷启动回灌）完全一样，
所以抽到这里实现一次，避免两份拷贝各自漂移。

对应文档：
    需求分析.md F2（内存记忆）/ F4（溯源）/ F5（token 统计）
    系统设计.md §1.6（溯源数据流）、§1.7（记忆与持久化设计）

流式事件（Agent 层产出语义事件，接口层负责序列化成 NDJSON）：
    {"c": "文本增量"}   正文
    {"s": [Source, …]}  溯源来源（本轮）
    {"u": {Usage}}      token 用量
"""

from __future__ import annotations

import logging
import operator
import time
from typing import Annotated, Any, AsyncIterator, Callable, Iterable, TypedDict
from uuid import uuid4

import tiktoken
from langchain_core.messages import (
    AIMessage,
    AIMessageChunk,
    AnyMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
    trim_messages,
)
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition

logger = logging.getLogger(__name__)

# 喂给模型前的上下文上限（token，估算）。超出即裁掉最老的消息。
#
# 为什么是 12000 而不是 设计文档 §1.7.6 写的 3000：
# 3000 这个数**小于单轮 RAG 问答本身的体量** —— 实测一次 retrieve_context
# 返回 5 条资料约 2178 字 ≈ 3000 tokens，光工具结果就把预算占满了。
# 配合下面 `allow_partial=False`，裁剪器会把「提问 + 工具结果」整段丢掉，
# 只留系统提示词，模型看不到问题和资料，只能回一句「您好，请问有什么可以帮您」。
# 这是个静默失效：不报错、不告警，回答却完全驴唇不对马嘴。
#
# 12000 的依据：qwen3-max 的上下文窗口 32k 以上，12000 只占约三分之一，
# 既容得下多轮历史，也留足输出空间。
MAX_CONTEXT_TOKENS = 12000

# 冷启动回灌的条数上限：防止超长会话一次性灌爆上下文窗口
MAX_CONTEXT_MESSAGES = 50

# tiktoken 的 cl100k_base 编码器。**这里刻意不用设计文档里的
# `token_counter=ollama_model`** —— 那条路走 BaseLanguageModel.get_token_ids()，
# 需要额外安装 transformers（未装，实测直接 ImportError）。
# 本机已装 tiktoken（F5 也要用它做本地模型的用量估算），复用它即可：
# 只用于「裁剪到多少条」这个安全阈值，不需要精确，中文按 cl100k 估算偏差可接受。
_ENCODING = tiktoken.get_encoding("cl100k_base")


def count_tokens(messages: BaseMessage | Iterable[BaseMessage]) -> int:
    """估算消息列表的 token 数。作为 trim_messages 的 token_counter 使用。"""
    if isinstance(messages, BaseMessage):
        messages = [messages]
    total = 0
    for m in messages:
        content = m.content
        if not isinstance(content, str):
            # 多模态消息的 content 是 list[dict]，只统计文本块
            content = "".join(
                block.get("text", "") for block in content if isinstance(block, dict)
            )
        total += len(_ENCODING.encode(content)) + 4  # +4 是每条消息的角色/分隔开销的粗略估计
    return total


class AgentState(TypedDict):
    """智能体状态。

    `sources` 用 `operator.add` 作为 reducer：一轮问答可能调用工具多次
    （比如先查图谱再补向量检索），每次都要把来源**追加**而不是覆盖
    （见 系统设计.md §1.6）。
    """

    messages: Annotated[list[AnyMessage], add_messages]
    sources: Annotated[list[dict], operator.add]


def _extract_text(content: Any) -> str:
    """把消息 content 统一成纯文本。

    Ollama 返回的 content 有时是 `[{"type": "text", "text": "…"}]` 这种块结构，
    直接当字符串用会得到一堆 dict 的 repr。
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            block.get("text", "") for block in content if isinstance(block, dict)
        )
    return ""


def _to_lc_message(record: dict) -> BaseMessage:
    """业务消息（库里的一行）→ LangChain 消息。

    只映射 user / assistant 两类。**工具调用过程不进上下文**：上一轮的最终
    回答里已经包含实体名（如「百日咳的常见症状包括…」），模型据此足以理解
    「那能吃什么」在问什么，重新检索一次的成本远低于把工具消息塞进上下文
    （见 系统设计.md §1.7.5）。
    """
    role = record.get("role")
    content = record.get("content") or ""
    if role == "user":
        return HumanMessage(content=content)
    return AIMessage(content=content)


class AgentRuntime:
    """一个智能体的运行实例：持有两张编译好的图与全部流式逻辑。

    两张图：
        _graph       挂了 MemorySaver，管多轮上下文（F2 的热路径）
        _stateless   不挂 checkpointer，供 use_memory=false 的单轮问答使用

    为什么用两张图而不是「用临时 thread_id 绕开记忆」：后者会在 checkpointer
    里堆一堆用完即弃的 thread，长期占用内存且没有清理时机。两张图语义清晰、
    零残留。
    """

    def __init__(
        self,
        name: str,
        system_prompt: str,
        tools: list,
        model,
        model_name: str | None = None,
    ):
        self.name = name
        self.system_prompt = system_prompt
        self.tools = tools
        self.model = model
        self.model_name = model_name or getattr(model, "model", None) or getattr(
            model, "model_name", None
        ) or name
        self._model_with_tools = model.bind_tools(tools)
        self._checkpointer = MemorySaver()
        self._graph = self._build(self._checkpointer)
        self._stateless = self._build(None)

    # ── 图装配 ──────────────────────────────────────────────────────────
    def _build(self, checkpointer):
        builder = StateGraph(AgentState)
        builder.add_node("agent", self._call_model)
        builder.add_node("tools", self._make_tools_node())
        builder.add_edge(START, "agent")
        builder.add_conditional_edges(source="agent", path=tools_condition)
        builder.add_edge("tools", "agent")
        return builder.compile(checkpointer=checkpointer)

    def _call_model(self, state: AgentState):
        # 裁剪只发生在**喂给模型之前**：checkpointer 里的列表与 MySQL 里的记录
        # 都保留完整历史，用户回看时仍能看到全部对话（见 系统设计.md §1.7.6）。
        history = trim_messages(
            state["messages"],
            max_tokens=MAX_CONTEXT_TOKENS,
            strategy="last",          # 保留最近的消息
            token_counter=count_tokens,
            include_system=True,
            allow_partial=False,
            # 保证裁剪后仍从「用户提问」开始。否则第一刀可能落在 assistant 消息上，
            # 模型会收到一个「以 AI 发言开头」的对话，部分模型会因此答非所问。
            start_on="human",
        )
        messages = [SystemMessage(content=self.system_prompt)] + self._guard(history, state["messages"])
        return {"messages": [self._model_with_tools.invoke(messages)]}

    @staticmethod
    def _guard(trimmed: list[BaseMessage], original: list[BaseMessage]) -> list[BaseMessage]:
        """兜底：裁剪结果里若没有用户提问，就从最后一条提问起重来。

        为什么必须有这道防线：`trim_messages(allow_partial=False)` 是「要么整条保留、
        要么整条丢弃」。当**单条消息自己就超过预算**时（工具返回一大段检索结果就是
        这种情形），它会从后往前一路丢光，连本轮提问一起丢掉 —— 最终只剩系统提示词。
        模型于是答非所问，而且**不报任何错**，排查时完全没有线索。

        宁可超出预算，也不能丢掉「用户问了什么」。超出预算是可见的（模型可能报
        上下文超限），丢掉提问是隐形的。
        """
        if any(isinstance(m, HumanMessage) for m in trimmed):
            return list(trimmed)

        for i in range(len(original) - 1, -1, -1):
            if isinstance(original[i], HumanMessage):
                logger.warning(
                    "上下文裁剪把本轮提问也裁掉了（预算 %d tokens），已回退为「保留最后一条提问起的全部消息」",
                    MAX_CONTEXT_TOKENS,
                )
                return list(original)[i:]
        return list(original)

    def _make_tools_node(self):
        """工具节点：跑 ToolNode，并把新产生的溯源信息收集进 state.sources。

        为什么包一层而不是直接用 ToolNode：ToolNode 只返回 messages，
        而 artifact 里的 sources 需要单独摘出来进状态（F4）。
        只遍历**本次新增**的消息，所以不会把上一轮的来源重复计入 ——
        `operator.add` 是累加 reducer，一旦重复收集，第二轮会报出第一轮的来源。
        """
        tool_node = ToolNode(self.tools)

        def tools_node(state: AgentState):
            result = tool_node.invoke(state)
            new_messages = result["messages"]
            collected: list[dict] = []
            for message in new_messages:
                artifact = getattr(message, "artifact", None)
                if isinstance(artifact, dict):
                    collected.extend(artifact.get("sources") or [])
            return {"messages": new_messages, "sources": collected}

        return tools_node

    # ── 冷启动回灌（F2 + F7 的衔接点）──────────────────────────────────
    def _rehydrate(
        self,
        config: dict,
        history_loader: Callable[[], list[dict]] | None,
    ) -> None:
        """checkpointer 里没有该会话的上下文时，从数据库一次性回灌。

        热路径（同一会话连续提问）直接返回，**零数据库开销**；
        冷路径只在「进程重启后首次打开某会话」时触发一次
        （见 系统设计.md §1.7.3）。
        """
        if history_loader is None:
            return

        snapshot = self._graph.get_state(config)
        if snapshot.values.get("messages"):
            return  # 热路径

        history = history_loader()
        if not history:
            return  # 全新会话，没什么可灌的

        messages = [_to_lc_message(r) for r in history][-MAX_CONTEXT_MESSAGES:]
        # ⚠️ update_state 必须**一次性**传入全部消息，不能写成
        #    `for m in history: graph.update_state(...)`。
        #    add_messages 是 reducer，循环调用会触发多次 checkpoint 写入，
        #    既慢又会在 checkpointer 里堆积大量中间快照（见 系统设计.md §1.7.4）。
        self._graph.update_state(config, {"messages": messages})
        logger.info("冷启动回灌：会话 %s 灌入 %d 条历史", config["configurable"]["thread_id"], len(messages))

    def delete_thread(self, conversation_id: str) -> None:
        """删除会话时同步清理内存上下文。

        不做这一步，被删会话的上下文会变成**幽灵数据**长期占用内存
        （见 系统设计.md §1.7.7）。
        """
        try:
            self._checkpointer.delete_thread(conversation_id)
        except Exception as exc:  # 清理失败不该影响删除接口的成败
            logger.warning("清理会话 %s 的内存上下文失败：%s", conversation_id, exc)

    # ── 流式问答 ────────────────────────────────────────────────────────
    async def stream(
        self,
        question: str,
        conversation_id: str | None = None,
        use_memory: bool = True,
        history_loader: Callable[[], list[dict]] | None = None,
    ) -> AsyncIterator[dict]:
        """跑一轮问答，产出语义事件流。

        conversation_id 即 checkpointer 的 thread_id（见 需求分析.md F2）。
        use_memory=False 时走无状态图，模型只看到本轮问题；
        注意**落库不受此影响** —— 是否入库由接口层决定，与是否带记忆无关。
        """
        started = time.perf_counter()

        if use_memory:
            thread_id = conversation_id or f"ephemeral-{uuid4()}"
            config = {"configurable": {"thread_id": thread_id}}
            graph = self._graph
            self._rehydrate(config, history_loader)
        else:
            config = None
            graph = self._stateless

        collected_sources: list[dict] = []
        usage_metadata: dict | None = None
        response_model: str | None = None

        async for chunk, metadata in graph.astream(
            {"messages": [HumanMessage(content=question)]},
            config=config,
            stream_mode="messages",
        ):
            # ① 工具消息：摘出本轮溯源。ToolMessage 走的是独立分支 ——
            #    它不是 AIMessageChunk，也不能当正文增量下发。
            if isinstance(chunk, ToolMessage):
                artifact = getattr(chunk, "artifact", None)
                if isinstance(artifact, dict):
                    collected_sources.extend(artifact.get("sources") or [])
                continue

            # ② 正文增量：只要 agent 节点产出的 AIMessageChunk。
            #    不加这个过滤会把工具节点的中间消息也当成回答吐给用户。
            if metadata.get("langgraph_node") != "agent":
                continue
            if not isinstance(chunk, AIMessageChunk):
                continue

            if getattr(chunk, "usage_metadata", None):
                usage_metadata = chunk.usage_metadata
            meta = chunk.response_metadata or {}
            response_model = meta.get("model_name") or meta.get("model") or response_model

            text = _extract_text(chunk.content)
            if text:
                yield {"c": text}

        # ③ 溯源与用量搭在内容流尾部下发，不新开接口（见 系统设计.md §1.3）。
        #    顺序固定：先 s 后 u（接口文档.md §3.4.3）。
        if collected_sources:
            yield {"s": collected_sources}

        usage = self._build_usage(usage_metadata, response_model, started)
        if usage:
            yield {"u": usage}

    @staticmethod
    def _build_usage(
        usage_metadata: dict | None, model_name: str | None, started: float
    ) -> dict | None:
        """组装 Usage 事件。

        没有 usage_metadata 就返回 None —— **不发 `u` 事件**。本地 Ollama
        在部分版本上不返回用量，前端必须把 `u` 当可选处理，否则会一直等
        （见 接口文档.md §3.4.6）。
        """
        if not usage_metadata:
            return None
        prompt = int(usage_metadata.get("input_tokens") or 0)
        completion = int(usage_metadata.get("output_tokens") or 0)
        total = int(usage_metadata.get("total_tokens") or (prompt + completion))
        return {
            "prompt": prompt,
            "completion": completion,
            "total": total,
            "model": model_name or "unknown",
            "latency_ms": int((time.perf_counter() - started) * 1000),
        }
