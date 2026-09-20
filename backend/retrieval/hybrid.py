"""检索层 · 混合检索与 RRF 融合（F3 主链路）。

对应 系统设计.md §1.5 的三段式：

                     query
          ┌────────────┴────────────┐
     jieba 分词                 nomic-embed
          ↓                         ↓
   BM25（rank_bm25）          FAISS 向量检索
     top 20 (稀疏)              top 20 (稠密)
          └────────────┬────────────┘
                       ↓
              RRF 融合（k=60）→ top 20
                       ↓
        DashScope gte-rerank 精排 → top 5
                       ↓
              结构化 content + sources

**为什么用 RRF 而不是加权求和**：BM25 分与余弦相似度量纲不可比，加权求和需要
先归一化，而归一化参数又要靠调参。RRF 只用排名不用分值，天然免调参
（见 系统设计.md §1.5）。
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

from llm.rerank import rerank
from retrieval.dense import get_dense_index, to_similarity
from retrieval.sparse import get_sparse_index
from utils.paths import rerank_config, retrieval_config

logger = logging.getLogger(__name__)


@dataclass
class Candidate:
    """一条融合后的候选文档。

    保留 dense_rank / sparse_rank / rerank_score 这些**中间过程**，
    是 F4 溯源的关键：演示时能说清「这条答案为什么排第一」——
    稠密排第 2、稀疏排第 5、融合后进重排、最终得分 0.83。
    这是把黑箱变白箱的材料（见 系统设计.md §1.6）。
    """

    index: int                      # 语料下标（FAISS 与 BM25 共用同一套编号）
    content: str                    # 分块原文
    metadata: dict                  # 至少含 name（疾病名）
    channel: str                    # hybrid | dense | sparse
    rrf_score: float = 0.0
    dense_rank: int | None = None
    sparse_rank: int | None = None
    dense_distance: float | None = None
    rerank_score: float | None = None

    @property
    def name(self) -> str:
        return str(self.metadata.get("name") or f"chunk-{self.index}")

    @property
    def score(self) -> float | None:
        """展示用相关度。

        有重排分数就以它为准（0-1 的交叉编码器打分，最可信）；
        没有则退化为 L2 距离的单调映射值，并在 meta 里标明这是相对值。
        """
        if self.rerank_score is not None:
            return round(self.rerank_score, 4)
        if self.dense_distance is not None:
            return round(to_similarity(self.dense_distance), 4)
        return None

    @property
    def snippet(self) -> str:
        """溯源卡片里展示的片段，截断到 200 字。"""
        text = self.content.strip().replace("\n", " ")
        return text[:200] + ("…" if len(text) > 200 else "")

    def to_source(self) -> dict:
        """转成溯源对象（接口文档.md §3.4.5 的 Source 结构）。

        `meta` 保留中间过程 —— 稠密排第几、稀疏排第几、重排给了多少分。
        这是把「为什么是这条」讲清楚的材料，也是 F4 里最有说服力的部分。
        """
        meta: dict = {"channel": self.channel}
        if self.dense_rank is not None:
            meta["dense_rank"] = self.dense_rank
        if self.sparse_rank is not None:
            meta["sparse_rank"] = self.sparse_rank
        if self.dense_distance is not None:
            meta["dense_distance"] = round(self.dense_distance, 4)
        if self.rerank_score is not None:
            meta["rerank_score"] = round(self.rerank_score, 4)
        meta["rrf_score"] = round(self.rrf_score, 6)

        return {
            "type": "vector",
            "name": self.name,
            "score": self.score,
            "snippet": self.snippet,
            "meta": meta,
        }


@dataclass
class HybridSearchResult:
    candidates: list[Candidate] = field(default_factory=list)
    rerank_enabled: bool = False
    rerank_used: bool = False
    stats: dict = field(default_factory=dict)


def rrf_fuse(rankings: list[list[int]], k: int = 60) -> dict[int, float]:
    """Reciprocal Rank Fusion：score(d) = Σ 1 / (k + rank_i(d))。

    rankings 是各路通道的**有序**下标列表（第 0 个即该通道的第 1 名）。
    排名从 1 开始计 —— 若从 0 开始，第 1 名会拿到 1/(k+0)，与第 2 名的差距
    被压缩，且与「未命中」的边界变模糊。
    """
    fused: dict[int, float] = {}
    for ranking in rankings:
        for position, doc_index in enumerate(ranking):
            fused[doc_index] = fused.get(doc_index, 0.0) + 1.0 / (k + position + 1)
    return fused


# 对齐校验只做一次（O(n) 全文比对，3 万条约 0.2s），之后该索引实例常驻
_alignment_checked: set[str] = set()


def _ensure_aligned(dense, sparse) -> None:
    key = str(dense.path)
    if key in _alignment_checked:
        return
    # 必须先显式加载：SparseIndex 的 chunks 是懒加载的，不先加载会是空列表，
    # 校验会报出「FAISS 29787 条 vs 语料 0 条」这种误导性的结论。
    sparse.ensure_loaded()
    dense.verify_alignment(sparse.chunks)
    _alignment_checked.add(key)


def hybrid_search(
    query: str,
    *,
    dense_top_k: int | None = None,
    sparse_top_k: int | None = None,
    rrf_k: int | None = None,
    fusion_top_k: int | None = None,
    rerank_top_n: int | None = None,
    use_rerank: bool = True,
) -> HybridSearchResult:
    """三段式混合检索。参数缺省时取 .env 的配置（见 utils/paths.retrieval_config）。"""
    cfg = retrieval_config()
    dense_top_k = dense_top_k if dense_top_k is not None else cfg["dense_top_k"]
    sparse_top_k = sparse_top_k if sparse_top_k is not None else cfg["sparse_top_k"]
    rrf_k = rrf_k if rrf_k is not None else cfg["rrf_k"]
    fusion_top_k = fusion_top_k if fusion_top_k is not None else cfg["fusion_top_k"]
    rerank_top_n = rerank_top_n if rerank_top_n is not None else 5

    dense = get_dense_index()
    sparse = get_sparse_index()
    _ensure_aligned(dense, sparse)

    stats: dict = {"dense_top_k": dense_top_k, "sparse_top_k": sparse_top_k, "rrf_k": rrf_k}

    # ── 第一段：两路并行召回 ──
    t0 = time.perf_counter()
    dense_hits = dense.search(query, dense_top_k)
    stats["dense_ms"] = round((time.perf_counter() - t0) * 1000, 1)
    stats["dense_hits"] = len(dense_hits)

    t0 = time.perf_counter()
    sparse_hits = sparse.search(query, sparse_top_k)
    stats["sparse_ms"] = round((time.perf_counter() - t0) * 1000, 1)
    stats["sparse_hits"] = len(sparse_hits)

    dense_ids = [i for i, _ in dense_hits]
    sparse_ids = [i for i, _ in sparse_hits]
    dense_rank = {i: r for r, i in enumerate(dense_ids, start=1)}
    sparse_rank = {i: r for r, i in enumerate(sparse_ids, start=1)}
    dense_dist = dict(dense_hits)

    # ── 第二段：RRF 融合 ──
    t0 = time.perf_counter()
    fused = rrf_fuse([dense_ids, sparse_ids], k=rrf_k)
    ordered = sorted(fused.items(), key=lambda kv: kv[1], reverse=True)[:fusion_top_k]
    stats["fusion_ms"] = round((time.perf_counter() - t0) * 1000, 1)
    stats["fused_count"] = len(fused)

    candidates: list[Candidate] = []
    for idx, rrf_score in ordered:
        content, meta = sparse.document(idx)
        dr, sr = dense_rank.get(idx), sparse_rank.get(idx)
        # 通道标记：两路都召回 → hybrid；只被一路召回 → 标出是哪一路。
        # 这个标记会原样进溯源卡片，前端据此说明「这条为什么被选进来」。
        if dr is not None and sr is not None:
            channel = "hybrid"
        elif dr is not None:
            channel = "dense"
        else:
            channel = "sparse"
        candidates.append(
            Candidate(
                index=idx,
                content=content,
                metadata=meta,
                channel=channel,
                rrf_score=rrf_score,
                dense_rank=dr,
                sparse_rank=sr,
                dense_distance=dense_dist.get(idx),
            )
        )

    stats["candidates"] = len(candidates)
    if not candidates:
        return HybridSearchResult(candidates=[], rerank_enabled=False, stats=stats)

    # ── 第三段：在线大模型重排（失败即降级）──
    rerank_cfg = __import__("utils.paths", fromlist=["rerank_config"]).rerank_config()
    stats["rerank_enabled"] = bool(rerank_cfg["enabled"])
    if use_rerank and rerank_cfg["enabled"]:
        t0 = time.perf_counter()
        hits = rerank(query, [c.content for c in candidates], top_n=rerank_top_n)
        stats["rerank_ms"] = round((time.perf_counter() - t0) * 1000, 1)
        if hits is not None:
            # 重排只对传入的候选集重新排序，不引入新文档
            reordered = [candidates[h.index] for h in hits if 0 <= h.index < len(candidates)]
            for hit in hits:
                if 0 <= hit.index < len(candidates):
                    candidates[hit.index].rerank_score = hit.relevance_score
            stats["rerank_used"] = True
            return HybridSearchResult(
                candidates=reordered,
                rerank_enabled=True,
                rerank_used=True,
                stats=stats,
            )
        stats["rerank_used"] = False
        stats["rerank_degraded"] = True
    else:
        stats["rerank_enabled"] = False
        stats["rerank_used"] = False

    # 降级路径：直接用 RRF 顺序，取前 rerank_top_n 条。
    # 条数与启用重排时保持一致，免得「重排挂了返回 20 条、正常返回 5 条」，
    # 让上游的上下文长度随服务可用性波动。
    return HybridSearchResult(
        candidates=candidates[:rerank_top_n],
        rerank_enabled=bool(rerank_cfg["enabled"]),
        rerank_used=False,
        stats=stats,
    )
