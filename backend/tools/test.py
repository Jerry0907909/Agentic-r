"""工具层冒烟测试：验证「混合检索链路」与「结构化返回」是否正常。

用法：
    cd backend && python tools/test.py
    cd backend && python tools/test.py 糖尿病能吃哪些食物
"""

import sys
from pathlib import Path

# 项目根加入模块搜索路径（唯一自举语句，说明见 utils/paths.py）
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.rag_tool import retrieve_context

if __name__ == "__main__":
    query = sys.argv[1] if len(sys.argv) > 1 else "百日咳是什么病"

    # 查看工具的元信息（LangGraph 会把这些描述喂给大模型）
    print(f"工具名：{retrieve_context.name}")
    print(f"入参  ：{retrieve_context.args}")
    print(f"返回  ：{retrieve_context.response_format}")
    print(f"描述  ：{retrieve_context.description[:60]}…\n")

    # 调用工具。response_format="content_and_artifact" 的工具必须传 ToolCall
    # 结构（图内 ToolNode 的调用形式）才能拿到带 artifact 的 ToolMessage；
    # 传普通 {"query": ...} 只会返回 content 字符串。
    msg = retrieve_context.invoke({
        "name": "retrieve_context",
        "id": "call_smoke",
        "type": "tool_call",
        "args": {"query": query},
    })

    print("-" * 72)
    print(f"【content · 给模型读】{len(msg.content)} 字")
    print(msg.content[:600])
    print("-" * 72)

    sources = msg.artifact["sources"]
    print(f"【sources · 给前端展示】共 {len(sources)} 条")
    for s in sources:
        meta = s["meta"]
        print(f"  · {s['name']}")
        print(f"    相关度={s['score']}  通道={meta.get('channel')}  "
              f"稠密第{meta.get('dense_rank')}  稀疏第{meta.get('sparse_rank')}")
        print(f"    {s['snippet'][:70]}…")
    print("-" * 72)
    print(f"【检索过程】{msg.artifact['stats']}")
