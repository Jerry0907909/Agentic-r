"""工具层：把混合检索封装成 LangGraph Agent 可调用的 Tool。

本次改造（F3 + F4）做了两件事：

1. **检索链路**：从「FAISS 纯稠密、固定取 top 3、拼成一个字符串」升级为
   「BM25 + 向量 → RRF 融合 → DashScope 重排」三段式（见 系统设计.md §1.5）。
   原来的实现在中文短查询与专有名词（药名、检查项）上召回差，且条数写死。

2. **返回结构**：从「裸字符串」改为 `(content, artifact)` 二元组。
   这是 F4 溯源的关键 —— 改造前来源信息在 `return "\\n\\n".join(parts)`
   那一刻就被丢掉了，前端无从展示。现在 content 给模型读，artifact 里的
   sources 原样穿过 ToolNode 进入 AgentState，一路流到前端。

为什么用 `response_format="content_and_artifact"` 而不是把 JSON 塞进字符串：
后者的 sources 会被模型读到，白占上下文 token，而且模型可能把它当成正文复述出来。
artifact 走的是 ToolMessage 的独立字段，模型看不见，前端拿得到。
"""

import sys
from pathlib import Path
from typing import Annotated

# 项目根加入模块搜索路径（唯一自举语句，说明见 utils/paths.py）
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from langchain_core.tools import tool

from retrieval.hybrid import hybrid_search
from utils.paths import require_index


@tool(response_format="content_and_artifact")
def retrieve_context(query: Annotated[str, "用来RAG检索的字段"]) -> tuple[str, dict]:
    """在医疗知识库中检索与用户问题相关的疾病说明文本。
    当需要查询疾病的概念、病因、预防措施、传染方式、治疗周期、治愈率、费用等
    描述性内容时，使用这个方法。若要查询实体之间的关系（如某病有哪些症状、
    能吃哪些食物），请改用 cypher_tool。"""
    result = hybrid_search(query)

    if not result.candidates:
        # 明确告知「没检索到」，而不是返回空串。空串会让模型以为检索成功、
        # 只是内容为空，进而凭空作答 —— 与提示词里「检索结果不足时如实告知」
        # 的要求正好相反。
        return "医疗知识库中未检索到与该问题相关的内容。", {"sources": []}

    # content：给模型读的上下文。带上疾病名，方便模型知道每段出自哪里。
    parts = [f"【{c.name}】{c.content}" for c in result.candidates]
    # artifact：给前端用的溯源信息，不占模型的上下文 token
    sources = [c.to_source() for c in result.candidates]

    return "\n\n".join(parts), {"sources": sources, "stats": result.stats}


if __name__ == "__main__":
    # 定义问题
    user_query = "百日咳是什么病"
    # 先显示实际用的是哪个语料 —— 排查「检索结果驴唇不对马嘴」时就看这一行
    print(f"当前语料：{require_index()}\n")
    # 注意调用方式：`response_format="content_and_artifact"` 的工具，只有传
    # **ToolCall 结构**（图内 ToolNode 的调用形式）才会装配出带 artifact 的
    # ToolMessage；传普通 {"query": ...} 只会拿到 content 字符串。
    msg = retrieve_context.invoke({
        "name": "retrieve_context",
        "id": "call_demo",
        "type": "tool_call",
        "args": {"query": user_query},
    })
    print("=" * 72)
    print("【给模型的 content】")
    print(msg.content[:500])
    print("=" * 72)
    print(f"【给前端的 sources】共 {len(msg.artifact['sources'])} 条")
    for s in msg.artifact["sources"]:
        print(f"  · {s['name']}  相关度={s['score']}  通道={s['meta']['channel']}")
    print("=" * 72)
    print("【检索过程】", msg.artifact["stats"])
