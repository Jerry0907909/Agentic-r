import asyncio
import sys
from pathlib import Path
from typing import Annotated,TypedDict

# 项目根加入模块搜索路径（唯一自举语句，说明见 utils/paths.py）
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from langchain_core.messages import AIMessageChunk,AnyMessage,HumanMessage,SystemMessage
from langgraph.graph import END,START,StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode,tools_condition
from llm.ollama_llm import ollama_model
from backend.tools.rag_tool import retrieve_context
from backend.tools.cypher_tool import cypher_tool

#提示词
SYSTEM_PROMPT = """
你是一个专业的中文问答助手，你需要根据给定的上下文回答问题。
"1.优先使用retrieve_context()函数获取的参考资料"
"2.回答应该基于检索的结果，如果检索结果不足，先如实告知用户，再结合自身知识回答"
"3.回答要结构化，条理清晰"
"4.如果遇到不确定问题，主动询问用户以确认需求"
"5.回答全程使用中文"
"6.涉及疾病、症状、药物、食物、检查项目、科室等实体之间的【关系】时（例如「百日咳有哪些症状」「糖尿病能吃哪些食物」「和某症状相似的疾病有哪些」），用cypher_tool()查询Neo4j医疗知识图谱"
"7.查询疾病的概念、病因、预防措施、治疗周期等【文本描述】时，用retrieve_context()做向量检索"
"8.cypher_tool()是只读的，不要生成CREATE/MERGE/DELETE/SET等写语句；不确定关系名时先用 CALL db.relationshipTypes() 查看"
"""

#可用工具
_tools = [retrieve_context, cypher_tool]
#绑定工具
_model_with_tools = ollama_model.bind_tools(_tools)

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
        #处理ollama模型返回的内容
        if isinstance(content, list):
            content = "".join(block.get("text", "") for block in content if isinstance(block, dict))
        if content:
            yield content

if __name__ == "__main__":
    async def _main():
        async for chunk in stream_agent("如何使用langgraph?"):
            print(chunk, end="", flush=True)

    asyncio.run(_main())