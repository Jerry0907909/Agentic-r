"""Deterministic NDJSON stream scenarios for frontend development."""

from __future__ import annotations

import asyncio
import json
from typing import AsyncIterator, Literal

NORMAL_DELAY_SECONDS = 0.03
SLOW_DELAY_SECONDS = 0.5


def encode_line(event: dict) -> str:
    return json.dumps(event, ensure_ascii=False) + "\n"


def build_sources(agent_type: Literal["rag", "graph"]) -> list[dict]:
    graph_source = {
        "type": "graph",
        "name": "Mock 医疗知识图谱",
        "score": None,
        "snippet": "Mock 图谱关系：疾病、症状与常见检查的演示数据。",
        "meta": {"source": "mock"},
    }
    if agent_type == "graph":
        return [graph_source]
    return [
        {
            "type": "vector",
            "name": "Mock 医疗文档",
            "score": 0.92,
            "snippet": "Mock 向量检索片段：用于验证来源卡片渲染。",
            "meta": {"source": "mock"},
        },
    ]


def build_usage(question: str, answer: str, delay: float) -> dict:
    prompt = max(1, len(question))
    completion = max(1, len(answer))
    return {
        "prompt": prompt,
        "completion": completion,
        "total": prompt + completion,
        "model": "mock-qwen3-max",
        "latency_ms": int(delay * 1000 * 3),
    }


async def stream_events(
    *,
    question: str,
    conversation_id: str,
    agent_type: Literal["rag", "graph"],
    is_new: bool,
) -> AsyncIterator[dict]:
    if "[mock:error]" in question:
        scenario = "error"
    elif "[mock:empty]" in question:
        scenario = "empty"
    elif "[mock:slow]" in question:
        scenario = "slow"
    else:
        scenario = "normal"

    delay = SLOW_DELAY_SECONDS if scenario == "slow" else NORMAL_DELAY_SECONDS
    if is_new:
        yield {"sid": conversation_id}

    chunks = (
        ["这是 ", "Mock 医疗健康回答，", "已检索医学资料用于验证回答与来源展示，不构成医疗建议。"]
        if agent_type == "rag"
        else ["这是 ", "Mock 知识图谱回答，", "用于验证疾病关系查询与来源展示，不构成医疗建议。"]
    )
    answer = ""
    for chunk in chunks:
        await asyncio.sleep(delay)
        answer += chunk
        yield {"c": chunk}
        if scenario == "error":
            yield {"err": "MockStreamError: 模拟流式响应中断"}
            return

    if scenario != "empty":
        yield {"s": build_sources(agent_type)}
    yield {"u": build_usage(question, answer, delay)}
