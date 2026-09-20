"""模型层 · 重排客户端：DashScope gte-rerank。

对应 需求分析.md F3 第三段与 系统设计.md ADR-5。

**为什么直调 HTTP 而不装 dashscope SDK**：`gte-rerank` 不走 OpenAI 兼容端点，
无法复用现有的 `ChatOpenAI` 客户端；而为了一个接口引入一整个 SDK 不划算。
项目已有 httpx（langchain 的传递依赖），且已确立 `trust_env=False` 规避
macOS 系统代理劫持的约定，直接沿用。

**降级是本模块的核心设计**：重排是「锦上添花」而不是「必要环节」。网络不通、
额度耗尽、未开通权限、返回格式变化 —— 任何一种情况都返回 None，由调用方
退化为「混合检索 + RRF 融合」结果直接返回，链路不中断，只降精度
（对应错误码 50004「不报错」，见 接口文档.md §1.5）。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

from utils.paths import require_env, rerank_config

logger = logging.getLogger(__name__)

# DashScope 原生接口（非 OpenAI 兼容端点）
RERANK_URL = "https://dashscope.aliyuncs.com/api/v1/services/rerank/text-rerank/text-rerank"

# 单次重排请求的超时。候选集 20 条、单条几百字，正常 1-3 秒；
# 给 10 秒足够，超时即降级 —— 演示时宁可少一层精排，也不能卡住不动。
TIMEOUT_SECONDS = 10.0


@dataclass
class RerankHit:
    """一条重排结果。index 是**传入 documents 列表中的下标**，不是语料下标。"""

    index: int
    relevance_score: float


class RerankUnavailable(RuntimeError):
    """重排不可用。仅用于日志与健康检查，**不应被抛给用户**。"""


def _client() -> httpx.Client:
    # trust_env=False 必须加：httpx 默认读取 macOS 系统代理（127.0.0.1:9674），
    # 会把请求转给代理导致 502。这是本项目踩过的坑，全项目外部调用统一沿用。
    return httpx.Client(trust_env=False, timeout=TIMEOUT_SECONDS)


def rerank(
    query: str,
    documents: list[str],
    top_n: int | None = None,
    model: str | None = None,
) -> list[RerankHit] | None:
    """对候选文档精排。

    返回按相关度降序的 RerankHit 列表；**任何失败都返回 None**（调用方降级）。
    返回 None 而不是抛异常，是刻意的：重排失败对用户应当无感，
    链路自动降级为 RRF 结果，只在服务端日志留痕。
    """
    cfg = rerank_config()
    if not cfg["enabled"]:
        logger.info("重排已通过 RERANK_ENABLED=false 关闭，使用 RRF 融合结果")
        return None

    if not documents:
        return []

    model = model or cfg["model"]
    top_n = top_n or cfg["top_n"]
    # top_n 不能超过候选数，否则 DashScope 返回 400
    top_n = min(top_n, len(documents))

    try:
        api_key = require_env("OPENAI_API_KEY")
    except RuntimeError as exc:
        logger.warning("重排跳过：%s", exc)
        return None

    payload = {
        "model": model,
        "input": {"query": query, "documents": documents},
        "parameters": {"return_documents": False, "top_n": top_n},
    }

    try:
        with _client() as client:
            resp = client.post(
                RERANK_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
        if resp.status_code != 200:
            # 保留真实响应体：401（Key 无效）/ 403（未开通模型权限）/ 429（限流）
            # 三种情况长得完全一样，吞掉就没法排查。
            logger.warning(
                "重排服务返回 %s，降级为 RRF 结果。响应：%s",
                resp.status_code,
                resp.text[:500],
            )
            return None

        data = resp.json()
        results = (data.get("output") or {}).get("results")
        if not isinstance(results, list):
            logger.warning("重排响应缺少 output.results，降级为 RRF 结果。原始响应：%s", str(data)[:500])
            return None

        hits = [
            RerankHit(index=int(r["index"]), relevance_score=float(r["relevance_score"]))
            for r in results
            if "index" in r and "relevance_score" in r
        ]
        if not hits:
            logger.warning("重排返回空结果，降级为 RRF 结果")
            return None

        hits.sort(key=lambda h: h.relevance_score, reverse=True)
        return hits

    except Exception as exc:
        # 网络不通 / 超时 / JSON 解析失败 …… 一律降级
        logger.warning("重排调用失败（%s: %s），降级为 RRF 结果", type(exc).__name__, exc)
        return None


def check_health() -> str:
    """供 /api/health 使用。返回 'ok' / 'disabled' / 错误描述。

    只做配置与凭据检查，**不发真实请求** —— 健康检查要能在演示前快速跑完，
    不该因为一次外网往返而变慢或受网络波动影响。
    """
    cfg = rerank_config()
    if not cfg["enabled"]:
        return "disabled"
    try:
        require_env("OPENAI_API_KEY")
    except RuntimeError as exc:
        return f"未配置 API Key：{exc}"
    return "ok"
