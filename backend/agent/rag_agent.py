"""智能体层：医疗健康 RAG 问答（单工具）。

模型只使用 `retrieve_context` 检索医学资料。知识图谱关系查询由
`cypher_agent` 独立负责。记忆、溯源、用量等通用逻辑在 `agent/runtime.py`。

**问答模型固定为云端 DashScope `qwen3-max`**（与 cypher_agent 一致）。
本地 Ollama 只负责词嵌入，不参与生成 —— 原因见 `llm/ollama_llm.py` 的模块说明。

对应 需求分析.md F2 / F3 / F4 / F5。
"""

import asyncio
import sys
from pathlib import Path
from typing import AsyncIterator, Callable

# 项目根加入模块搜索路径（唯一自举语句，说明见 utils/paths.py）
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.runtime import AgentRuntime
from llm.qwen_llm import MyModel
from tools.rag_tool import retrieve_context

# 提示词
SYSTEM_PROMPT = """
你是一个专业的中文医疗健康问答助手，你需要根据检索到的医学资料回答用户的症状、疾病、用药与日常健康问题。
"1.优先使用retrieve_context()函数获取的参考资料"
"2.回答应该基于检索的结果，如果检索结果不足，先如实告知用户，再结合自身知识回答"
"3.回答要结构化，条理清晰"
"4.如果遇到不确定问题，主动询问用户以确认需求"
"5.回答全程使用中文"
"6.不要调用或模拟知识图谱查询；疾病实体关系问题由独立的知识图谱查询模式处理"
"7.回答末尾提示用户可查看医学资料来源，不要把自身知识伪装成检索来源"
"""

# 可用工具
TOOLS = [retrieve_context]

# 问答模型：云端 DashScope（本地 Ollama 只做词嵌入，见模块 docstring）
_model = MyModel.get_model()

# 全局运行时（内含两张编译好的图：带记忆 / 无记忆）
runtime = AgentRuntime(
    name="rag",
    system_prompt=SYSTEM_PROMPT,
    tools=TOOLS,
    model=_model,
    model_name=str(getattr(_model, "model_name", "qwen3-max")),
)


async def stream_agent(
    question: str,
    conversation_id: str | None = None,
    use_memory: bool = True,
    history_loader: Callable[[], list[dict]] | None = None,
) -> AsyncIterator[dict]:
    """流式问答，产出 `{"c"|"s"|"u": ...}` 事件。

    conversation_id 即 checkpointer 的 thread_id。history_loader 只在
    「进程重启后首次访问该会话」时被调用一次（冷启动回灌）。
    """
    async for event in runtime.stream(
        question=question,
        conversation_id=conversation_id,
        use_memory=use_memory,
        history_loader=history_loader,
    ):
        yield event


def delete_thread(conversation_id: str) -> None:
    """删除会话时同步清理内存上下文（见 系统设计.md §1.7.7）。"""
    runtime.delete_thread(conversation_id)


if __name__ == "__main__":
    async def _main():
        question = "百日咳有哪些症状？"
        print(f"问题：{question}\n")
        async for event in stream_agent(question, conversation_id="demo-thread"):
            if "c" in event:
                print(event["c"], end="", flush=True)
            elif "s" in event:
                print(f"\n\n【溯源】{len(event['s'])} 条")
                for s in event["s"]:
                    print(f"  · [{s['type']}] {s['name']}  相关度={s['score']}")
            elif "u" in event:
                print(f"\n【用量】{event['u']}")

    asyncio.run(_main())
