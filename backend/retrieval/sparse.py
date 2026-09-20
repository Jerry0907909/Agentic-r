"""检索层 · 稀疏通道：jieba 分词 + rank_bm25。

为什么需要这一路：改造前的 `rag_tool` 是纯稠密检索（FAISS + nomic-embed-text），
中文短查询与专有名词（药名、检查项）召回差 —— 这类查询要的是**关键词精确匹配**，
而稠密向量恰恰会把「百日咳」和「白喉」这类近义病名混在一起。
两路互补，融合后召回更稳（见 系统设计.md §1.5）。

分词函数 `tokenize` 在这里定义一次，索引构建（utils/rag_index.py）与查询
（本模块）都调它 —— 两边分词方式不一致是 BM25 最隐蔽的 bug：索引里是
「百日咳」、查询时切成「百日 / 咳」，词对不上，分数全为 0，且不报任何错。
"""

from __future__ import annotations

import pickle
from pathlib import Path

import jieba
from rank_bm25 import BM25Plus

from utils.paths import require_bm25_corpus

# 语料文件版本号。格式变更时递增，加载端据此拒绝旧格式并提示重建，
# 免得出现「读到旧结构 → KeyError」这种看不出原因的崩溃。
CORPUS_VERSION = 1

# 用 BM25Plus 而不是更常见的 BM25Okapi，理由是「分数 > 0 必须等价于命中」：
#
# BM25Okapi 的 idf = ln((N - freq + 0.5) / (freq + 0.5))，当某个词出现在
# **超过一半**文档里时 idf ≤ 0，该词对分数的贡献归零甚至为负（rank_bm25 会把
# 负值抬到一个小的 epsilon，但**恰好为 0 的不动**）。于是「真实命中的文档」
# 和「完全没命中的文档」都会拿到 0 分，两者无法区分。
#
# 实测踩到过：小语料下查「百日咳有哪些症状」返回 0 条 —— 因为「百日咳」在
# 6 篇里出现 3 次，idf 正好为 0，命中的 3 篇全被 `score > 0` 当成未命中丢掉。
# 30k 语料下不容易触发，但这是个会静默丢召回的隐患，不该留着。
#
# BM25Plus 的 idf = ln((N + 1) / freq) 恒为正，delta 项也恒为正，因此
# 「score > 0」与「文档至少命中一个查询词」严格等价，过滤条件才有意义。
# RRF 只用排名不用分值，换变体不影响融合结果（见 系统设计.md §1.5）。


def tokenize(text: str) -> list[str]:
    """中英文混合分词。索引与查询共用此函数（见模块 docstring）。

    用 `lcut_for_search` 而不是 `lcut`：它会把长词再切出子词
    （「百日咳」→ 百日咳 / 百日 / 咳），提升短查询的召回。这是 jieba 官方
    对搜索引擎索引场景的推荐模式。

    过滤空白 token；保留纯数字与单字 —— 医疗语料里「Ⅲ」「2∶1」这类
    片段是有信息量的，不要按长度一刀切掉。
    """
    return [t.strip() for t in jieba.lcut_for_search(text) if t.strip()]


class SparseIndex:
    """BM25 稀疏索引。进程内单例式使用，加载一次后常驻。

    语料来源：<索引目录>/bm25_corpus.pkl，由 utils/rag_index.py 构建 FAISS 时
    一并落盘（FAISS 只存向量，BM25 要的是原始文本，两者必须同源同序，
    否则融合时「第 i 条」在两边指向的不是同一段文本）。
    """

    def __init__(self, corpus_path: Path | None = None):
        self._path = Path(corpus_path) if corpus_path else require_bm25_corpus()
        self._bm25: BM25Plus | None = None
        # 与 FAISS 索引严格同序：chunks[i] / metadatas[i] / tokens[i] 指同一段文本
        self.chunks: list[str] = []
        self.metadatas: list[dict] = []
        self.tokens: list[list[str]] = []

    # ── 加载 ────────────────────────────────────────────────────────────
    def ensure_loaded(self) -> None:
        """显式触发加载。

        必须对外暴露：`chunks` / `metadatas` / `tokens` 三个属性在加载前都是**空列表**
        而不是「未定义」，外部直接读不会报错、只会静默拿到空数据。
        hybrid 的 FAISS↔BM25 对齐校验就踩过这个坑 —— 它读 `sparse.chunks` 时
        还没发生过任何检索，于是拿到 0 条，报出「FAISS 29787 条 vs 语料 0 条」
        这种看起来像索引损坏、实际是加载顺序问题的错误。
        """
        self._ensure_loaded()

    def _ensure_loaded(self) -> None:
        if self._bm25 is not None:
            return

        if not self._path.exists():
            raise FileNotFoundError(
                f"BM25 语料不存在：{self._path}\n"
                f"请重新构建索引（会同时产出 FAISS 与 BM25 两份产物）："
                f"python utils/rag_index.py medical"
            )

        with self._path.open("rb") as f:
            payload = pickle.load(f)

        version = payload.get("version")
        if version != CORPUS_VERSION:
            raise RuntimeError(
                f"BM25 语料格式版本不匹配：文件为 v{version}，当前代码期望 v{CORPUS_VERSION}。\n"
                f"请重新构建索引：python utils/rag_index.py medical"
            )

        self.chunks = payload["chunks"]
        self.metadatas = payload["metadatas"]
        self.tokens = payload["tokens"]

        if not (len(self.chunks) == len(self.metadatas) == len(self.tokens)):
            raise RuntimeError(
                f"BM25 语料内部长度不一致：chunks={len(self.chunks)} "
                f"metadatas={len(self.metadatas)} tokens={len(self.tokens)}"
            )

        self._bm25 = BM25Plus(self.tokens)

    # ── 查询 ────────────────────────────────────────────────────────────
    def search(self, query: str, top_k: int) -> list[tuple[int, float]]:
        """返回 [(语料下标, BM25 分数)]，按分数降序，最多 top_k 条。

        下标与 FAISS 索引同序，供 RRF 融合时对齐两条通道的「同一条候选」。
        """
        self._ensure_loaded()
        assert self._bm25 is not None

        q_tokens = tokenize(query)
        if not q_tokens:
            return []

        scores = self._bm25.get_scores(q_tokens)
        # 只取正分。BM25Plus 的 idf 与 delta 项恒为正，因此「分数 > 0」严格等价于
        # 「该文档至少命中一个查询词」—— 见模块顶部关于为什么不用 BM25Okapi 的说明。
        ranked = [(i, float(s)) for i, s in enumerate(scores) if s > 0]
        ranked.sort(key=lambda x: x[1], reverse=True)
        return ranked[:top_k]

    @property
    def size(self) -> int:
        self._ensure_loaded()
        return len(self.chunks)

    def document(self, idx: int) -> tuple[str, dict]:
        """按下标取原文与元数据，用于组装溯源信息。"""
        self._ensure_loaded()
        return self.chunks[idx], self.metadatas[idx]


# 进程内缓存：BM25 语料解包 + 建索引不便宜（3 万块），每次查询都重建会拖垮响应
_cache: dict[str, SparseIndex] = {}


def get_sparse_index(corpus_path: Path | None = None) -> SparseIndex:
    key = str(corpus_path or require_bm25_corpus())
    if key not in _cache:
        _cache[key] = SparseIndex(corpus_path)
    return _cache[key]
