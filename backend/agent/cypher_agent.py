"""智能体层：医疗疾病问答（单图谱工具）。

与 `rag_agent` 的差别只有三处：工具集仅 `cypher_tool`、模型固定为云端 Qwen、
提示词要求「必须先查再答」。为什么图谱问答要用云端模型：生成 Cypher 语句需要
较强的代码与模式理解能力，本地 4B 模型不足以胜任（见 接口文档.md §3.1）。

对应 需求分析.md F6。
"""

import asyncio
import sys
from pathlib import Path
from typing import AsyncIterator, Callable

# 项目根加入模块搜索路径（唯一自举语句，说明见 utils/paths.py）
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.runtime import AgentRuntime
from llm.qwen_llm import MyModel
from tools.cypher_tool import cypher_tool

# 提示词
SYSTEM_PROMPT = """
一、你是一个疾病查询助手，你只有一个工具
    cypher_tool:cypher语句查询
    （只读，只能查询，不能新增/修改/删除数据）
二、工作流程：你必须严格按照以下步骤执行
    1 用户问题：你必须调用工具来查询问题，不要凭空回答
    2 不确定关系名或标签名时，先用cypher_tool执行 CALL db.relationshipTypes()
      或 CALL db.labels() 查看，再写正式查询
三、反馈信息
    1 用查到的数据回答，回答要结构化，条理清晰
    2 如果工具查不到数据，请直接告诉用户不知道，其他文本信息不需要
    3 回答全程使用中文
"""

# 可用工具：只有图谱查询
TOOLS = [cypher_tool]

_model = MyModel.get_model()

runtime = AgentRuntime(
    name="graph",
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
    """流式问答，产出 `{"c"|"s"|"u": ...}` 事件。接口与 rag_agent 完全一致。"""
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
        async for event in stream_agent(question, conversation_id="demo-thread-graph"):
            if "c" in event:
                print(event["c"], end="", flush=True)
            elif "s" in event:
                print(f"\n\n【溯源】{len(event['s'])} 条")
                for s in event["s"]:
                    print(f"  · [{s['type']}] {s['name']}  相关度={s['score']}")
            elif "u" in event:
                print(f"\n【用量】{event['u']}")

    asyncio.run(_main())
