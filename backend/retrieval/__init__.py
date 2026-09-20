"""检索层：稀疏（BM25）+ 稠密（FAISS）双通道检索与 RRF 融合。

对应 需求分析.md F3 与 系统设计.md §1.5。

对外入口只有一个：

    from retrieval.hybrid import hybrid_search
    results = hybrid_search("百日咳有哪些症状")
"""
