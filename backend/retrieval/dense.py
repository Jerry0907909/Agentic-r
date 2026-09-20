"""检索层 · 稠密通道：FAISS 向量检索。

这一路是改造前 `rag_tool` 唯一在做的事，本次保留不动（语义召回能力本来就
是它的强项），只是把返回值从「拼好的字符串」改成「带下标与分数的候选列表」，
以便与稀疏通道做 RRF 融合（见 系统设计.md §1.5）。

**关键约束：FAISS 的 id 必须与 BM25 语料的下标严格同序。**
两个索引由 utils/rag_index.py 从同一个 chunks 列表派生，理论上天然对齐；
但 `merge_from` 分批合并、`save_local` / `load_local` 往返之后，顺序是否
真的保持，不该靠「理论上」—— 所以这里加载后做一次实测校验，不一致就直接
报错，而不是让融合悄悄把两段不同的文本当成同一条候选。
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from langchain_community.vectorstores import FAISS

from llm.ollama_llm import ollama_embedding
from utils.paths import require_index


def _resolve_index_dir(index_dir: str | Path | None) -> Path:
    """把「语料名 / 索引目录 / None」统一解析成存在的索引目录。

    - None      → 取 .env 的 FAISS_INDEX_NAME（默认 medical）
    - 语料名     → 走 utils.paths 的注册表校验
    - 目录路径   → 直接用，只校验存在性

    这个函数存在的原因：`get_dense_index()` 内部拿到的是**已解析的 Path**，
    若直接把它再交给 `require_index()`（那是个「按语料名查表」的函数），
    会报「未知的语料名 /…/faiss-index/medical」—— 路径被当成了名字。
    """
    if index_dir is None:
        return require_index()

    # 语料名不带路径分隔符，据此区分「名字」与「路径」
    text = str(index_dir)
    if "/" not in text and "\\" not in text:
        return require_index(text)

    path = Path(index_dir)
    if not path.exists():
        raise FileNotFoundError(
            f"向量库不存在：{path}\n请先构建：python utils/rag_index.py medical"
        )
    return path


class DenseIndex:
    """FAISS 稠密索引。进程内缓存，加载一次后常驻。"""

    def __init__(self, index_dir: str | Path | None = None):
        path = _resolve_index_dir(index_dir)
        self.path = path
        self.vectorstore = FAISS.load_local(
            str(path), ollama_embedding, allow_dangerous_deserialization=True
        )
        # FAISS 的 IndexFlatL2：返回的是**平方 L2 距离**，越小越相关。
        # 不是余弦相似度，因此不能直接当「相似度 0.83」展示，需要转换（见 to_similarity）。
        self.dimension = self.vectorstore.index.d

    # ── 查询 ────────────────────────────────────────────────────────────
    def search(self, query: str, top_k: int) -> list[tuple[int, float]]:
        """返回 [(FAISS id, 距离)]，按距离升序（即相关度降序），最多 top_k 条。

        用 `index.search` 直接拿 id，而不是 `similarity_search`：后者只回
        Document，拿不到下标，就没法与稀疏通道对齐做融合。
        """
        vec = self.vectorstore.embedding_function.embed_query(query)
        matrix = np.asarray(vec, dtype="float32").reshape(1, -1)
        distances, ids = self.vectorstore.index.search(matrix, top_k)
        # -1 是 FAISS 在「库里条目少于 top_k」时的填充值，必须剔除，
        # 否则下标 -1 会静默指向语料的最后一条（Python 负索引！），
        # 融合结果里凭空多出一条毫不相关的候选。
        return [(int(i), float(d)) for i, d in zip(ids[0], distances[0]) if int(i) != -1]

    @property
    def size(self) -> int:
        return int(self.vectorstore.index.ntotal)

    # ── 与 BM25 语料的对齐校验 ──────────────────────────────────────────
    def verify_alignment(self, chunks: list[str]) -> None:
        """校验 FAISS 的 id 顺序与 BM25 语料下标一一对应。

        逐条比对全文，代价是 O(n) 次字符串比较（3 万条实测 < 0.2s），
        只在首次查询时做一次。不一致就抛错 —— 这种情况下的融合结果
        「看起来有结果、实际上张冠李戴」，比直接报错危险得多。
        """
        if self.size != len(chunks):
            raise RuntimeError(
                f"FAISS 索引与 BM25 语料条数不一致：FAISS {self.size} 条，语料 {len(chunks)} 条。\n"
                f"两个产物必须由同一次 `python utils/rag_index.py medical` 生成，"
                f"请重新构建索引。"
            )

        mapping = self.vectorstore.index_to_docstore_id
        for i, text in enumerate(chunks):
            key = mapping.get(i)
            if key is None:
                raise RuntimeError(f"FAISS 索引缺少 id={i} 的映射，索引文件可能损坏。")
            doc = self.vectorstore.docstore.search(key)
            if getattr(doc, "page_content", None) != text:
                raise RuntimeError(
                    f"FAISS 索引与 BM25 语料在下标 {i} 处不一致：\n"
                    f"  FAISS：{getattr(doc, 'page_content', None)!r:.80}\n"
                    f"  语料 ：{text!r:.80}\n"
                    f"两个产物不同源，融合会把两段不同的文本当成同一条候选。"
                    f"请重新构建索引：python utils/rag_index.py medical"
                )


def to_similarity(distance: float) -> float:
    """把平方 L2 距离单调映射到 (0, 1] 的「相对相关度」，仅供展示。

    为什么要转换：溯源卡片（F4）要展示「相似度 0.83」这种人类可读的数字，
    而 FAISS 给的是 L2 距离（越小越好、上不封顶），直接展示会让人误以为
    「0.83 表示 83% 相似」。

    注意这只是**相对**相关度，不是概率、也不是余弦相似度，不要拿去做阈值判断。
    真正的精排分数由 DashScope 重排提供（见 llm/rerank.py），有重排结果时
    以重排分数为准。
    """
    return float(1.0 / (1.0 + max(distance, 0.0)))


# 进程内缓存：FAISS 加载 + 对齐校验不便宜，每次查询都重做会拖垮响应
_cache: dict[str, DenseIndex] = {}


def get_dense_index(index_dir: str | Path | None = None) -> DenseIndex:
    path = _resolve_index_dir(index_dir)
    key = str(path)
    if key not in _cache:
        _cache[key] = DenseIndex(path)
    return _cache[key]
