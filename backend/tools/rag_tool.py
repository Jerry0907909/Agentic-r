"""工具层：把向量库检索封装成 LangGraph Agent 可调用的 Tool"""

import sys
from pathlib import Path
from typing import Annotated

# 项目根加入模块搜索路径（唯一自举语句，说明见 utils/paths.py）
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from langchain_community.vectorstores import FAISS
from langchain_core.tools import tool

from llm.ollama_llm import ollama_embedding
from backend.utils.paths import require_index

# 全局变量，缓存FAISS向量库实例
_vectorstore = None


def _get_vectorstore():
    """加载向量库。用哪个语料由 .env 的 FAISS_INDEX_NAME 决定，缺省 medical。

    这里刻意用 utils.paths.require_index()，而不是自己拼路径 + `os.getenv(name, "default")`：
    以前 .env 里压根没有 FAISS_INDEX_NAME 这一项，getenv 就静默回退到 default
    （Spring Boot 语料），于是工具说明写着「在医疗知识库中检索」、实际检索的却是
    Spring Boot 文档，全程不报任何错 —— 模型照着错的上下文答题，最难查的那种。
    现在索引缺失会直接抛 FileNotFoundError 并给出构建命令，不会再悄悄换语料。

    另外：延迟到调用时才解析（不在 import 时），这样向量库还没构建好时，
    agent 仍能正常启动并使用 cypher_tool。
    """
    global _vectorstore
    if _vectorstore is None:
        path = require_index()
        _vectorstore = FAISS.load_local(
            str(path), ollama_embedding, allow_dangerous_deserialization=True
        )
    return _vectorstore


@tool
#RAG检索函数
def retrieve_context(query: Annotated[str, "用来RAG检索的字段"]) -> str:
    """在医疗知识库中检索与用户问题相关的疾病说明文本。
    当需要查询疾病的概念、病因、预防措施、传染方式、治疗周期、治愈率、费用等
    描述性内容时，使用这个方法。若要查询实体之间的关系（如某病有哪些症状、
    能吃哪些食物），请改用 cypher_tool。"""
    #获取向量库实例
    vectorstore = _get_vectorstore()
    #稠密向量相似度检索
    results = vectorstore.similarity_search(query, k=3)
    #带上疾病名，方便模型知道每段文字出自哪个疾病
    parts = []
    for doc in results:
        name = doc.metadata.get("name")
        parts.append(f"【{name}】{doc.page_content}" if name else doc.page_content)
    return "\n\n".join(parts)


if __name__ == "__main__":
    #定义问题
    user_query = "百日咳是什么病"
    #先显示实际用的是哪个语料 —— 排查「检索结果驴唇不对马嘴」时就看这一行
    print(f"当前语料：{require_index()}\n")
    #调用函数：@tool 装饰后是 StructuredTool，需用 invoke 传参
    print(retrieve_context.invoke({"query": user_query}))
