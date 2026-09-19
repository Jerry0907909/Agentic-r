import asyncio
import sys
from pathlib import Path
from typing import Annotated,TypedDict

# 项目根加入模块搜索路径（唯一自举语句，说明见 utils/paths.py）
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from langchain_core.messages import AIMessageChunk,AnyMessage,HumanMessage,SystemMessage
from langgraph.graph import START,StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode,tools_condition
# 模型层：图谱问答要生成 Cypher，用云端 qwen 比本地 4B 模型靠谱
from backend.llm.qwen_llm import MyModel
from backend.tools.cypher_tool import cypher_tool

#提示词
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

#可用工具
_tools = [cypher_tool]
#绑定工具
_model_with_tools = MyModel.get_model().bind_tools(_tools)

# 1.定义状态
class AgentState(TypedDict):
    messages:Annotated[list[AnyMessage],add_messages]

# 2.定义节点:调用模型
def call_model(state:AgentState):
    #拼接系统提示词+历史对话消息
    messages = [SystemMessage(content=SYSTEM_PROMPT)] + state["messages"]
    #调用模型
    response = _model_with_tools.invoke(messages)
    #返回新的AI消息
    return {"messages":[response]}

# 3.构建langgraph状态图
def _build_graph():
    #创建状态图构建器
    builder = StateGraph(AgentState)
    #添加节点
    builder.add_node("agent", call_model)
    #添加工具节点
    builder.add_node("tools", ToolNode(_tools))
    #添加普通边
    builder.add_edge(START, "agent")
    #添加条件边: agent节点结束后, 使用tools_condition做路由判断
    builder.add_conditional_edges(source="agent", path=tools_condition)
    #添加普通边
    builder.add_edge("tools", "agent")
    #编译图
    return builder.compile()

#全局图实例
_graph = _build_graph()
def _get_graph():
    global _graph
    if _graph is None:
        _graph = _build_graph()
    return _graph

async def stream_agent(question: str):
    graph = _graph
    async for chunk, metadata in graph.astream(
        input={"messages":[HumanMessage(content=question)]},
        stream_mode = "messages",
    ):
        if metadata.get("langgraph_node") != "agent":
            continue
        if not isinstance(chunk, AIMessageChunk):
            continue
        content = chunk.content
        #处理模型返回的内容
        if isinstance(content, list):
            content = "".join(block.get("text", "") for block in content if isinstance(block, dict))
        if content:
            yield content

if __name__ == "__main__":
    async def _main():
        async for chunk in stream_agent("百日咳有哪些症状？"):
            print(chunk, end="", flush=True)

    asyncio.run(_main())
