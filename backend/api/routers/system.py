"""接口层 · L3 系统域：依赖健康检查。

对应 接口文档.md §5。用途是**演示前跑一次** —— 比现场发现 Neo4j 没启动强。

设计要点：**该接口始终返回 200**，即使部分依赖异常。因为「服务本身活着、
某个依赖挂了」是有价值的信息，返回 5xx 反而让调用方以为整个服务不可用。
判断依据是各字段的值，不是 HTTP 状态码。
"""

from __future__ import annotations

import os

import httpx
from fastapi import APIRouter
from sqlalchemy import text

from api.schemas import HealthStatus
from db.session import engine
from llm.rerank import check_health as rerank_health
from utils.paths import (
    DEFAULT_INDEX,
    bm25_corpus_path,
    index_path,
    require_env,
)

router = APIRouter()

# 各依赖的探测超时。健康检查要能快速返回，不能因为某个依赖卡住而整体挂起。
PROBE_TIMEOUT = 3.0


def _check_mysql() -> str:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return "ok"
    except Exception as exc:
        return f"{type(exc).__name__}: {exc}"


def _check_neo4j() -> str:
    try:
        from neo4j import GraphDatabase

        driver = GraphDatabase.driver(
            require_env("NEO4J_BOLT_URL"),
            auth=(require_env("NEO4J_USER"), require_env("NEO4J_PASSWORD")),
        )
        try:
            driver.verify_connectivity()
        finally:
            driver.close()
        return "ok"
    except Exception as exc:
        return f"{type(exc).__name__}: {exc}"


def _check_ollama() -> str:
    try:
        # trust_env=False：同项目既有约定，规避 macOS 系统代理劫持导致 502
        with httpx.Client(trust_env=False, timeout=PROBE_TIMEOUT) as client:
            resp = client.get("http://127.0.0.1:11434/api/tags")
        if resp.status_code != 200:
            return f"HTTP {resp.status_code}"
        models = [m.get("name") for m in (resp.json().get("models") or [])]
        return "ok" if models else "ok（无已拉取模型）"
    except Exception as exc:
        return f"{type(exc).__name__}: {exc}"


def _check_faiss() -> str:
    """返回当前生效的语料名；目录不存在则给出错误描述。"""
    name = os.getenv("FAISS_INDEX_NAME") or DEFAULT_INDEX
    path = index_path(name)
    if not path.exists():
        return f"语料 {name} 未构建（{path}）"
    return name


def _check_bm25() -> str:
    path = bm25_corpus_path()
    return "ok" if path.exists() else "missing"


@router.get(
    "/health",
    response_model=HealthStatus,
    summary="依赖健康检查",
    description="演示前跑一次。始终返回 200，靠字段值判断哪个依赖异常。",
)
def health() -> HealthStatus:
    return HealthStatus(
        mysql=_check_mysql(),
        neo4j=_check_neo4j(),
        ollama=_check_ollama(),
        faiss_index=_check_faiss(),
        bm25_corpus=_check_bm25(),
        rerank=rerank_health(),
    )
