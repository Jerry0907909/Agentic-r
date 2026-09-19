"""工具层冒烟测试：直接调用 rag_tool 里的检索工具，验证「向量库 - 嵌入模型」链路可用"""

import sys
from pathlib import Path

# 项目根加入模块搜索路径（唯一自举语句，说明见 utils/paths.py）
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.tools.rag_tool import retrieve_context

if __name__ == "__main__":
    # 查看工具的元信息（LangGraph 会把这些描述喂给大模型）
    print(f"工具名：{retrieve_context.name}")
    print(f"入参：{retrieve_context.args}")
    print(f"描述：{retrieve_context.description}\n")

    # 调用工具
    context = retrieve_context.invoke({"query": "百日咳是什么病"})
    print("-" * 60)
    print(context)
