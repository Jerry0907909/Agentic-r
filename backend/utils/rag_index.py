"""数据层：构建 FAISS 向量库（加载文档 - 切分 - 向量化 - 落盘）

支持两种语料：
    springboot（默认，保持原行为）—— utils/docs/springboot-intro.md
    medical                      —— 从 Neo4j 医疗知识图谱读取疾病文本

用法：
    python utils/rag_index.py                 # 构建 springboot 索引 -> faiss-index/default
    python utils/rag_index.py medical         # 构建医疗索引      -> faiss-index/medical
    python utils/rag_index.py medical --chunk-size 500
"""

import argparse
import shutil
import sys
from pathlib import Path
from typing import List

# 项目根加入模块搜索路径（唯一自举语句，说明见 utils/paths.py）
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from langchain_community.document_loaders import UnstructuredMarkdownLoader
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from llm.ollama_llm import ollama_embedding
from backend.utils.paths import PROJECT_ROOT, index_path, require_env

# 源文档在本包内，直接用项目根拼；向量库路径一律问 utils.paths 要，不在这里自己拼
DOC_PATH = PROJECT_ROOT / "utils" / "docs" / "springboot-intro.md"
INDEX_PATH = index_path("default")
# 医疗语料索引单独放一个目录，不覆盖原来的 default 索引
MEDICAL_INDEX_PATH = index_path("medical")

# 每批向量化的文本块数。实测（本机 nomic-embed-text）：
#   500 条 -> 必被 Ollama 的 runner 以 400/EOF 拒绝
#   256 条 -> 稳定
# 取 128 留出余量；吞吐与 256 相同，约 24.5 条/秒（医疗语料 29787 块 ≈ 20 分钟）。
BATCH_SIZE = 128
# 折半重试的下限：再小就不再拆，直接抛出
MIN_BATCH_SIZE = 8

# 疾病节点里值得进向量库的文本字段（顺序即拼装顺序）
MEDICAL_FIELDS = [
    ("疾病描述", "desc"),
    ("病因", "cause"),
    ("预防", "prevent"),
    ("传染方式", "get_way"),
    ("治疗周期", "cure_lasttime"),
    ("治愈率", "cured_prob"),
    ("医保", "yibao_status"),
    ("费用", "cost_money"),
]


# 文档加载函数
def load_document():
    loader = UnstructuredMarkdownLoader(str(DOC_PATH))
    docs = loader.load()
    print(f"加载到 {len(docs)} 个文档对象")
    return docs


# 医疗语料加载：从 Neo4j 读疾病文本，一个疾病一个 Document
def load_medical_documents():
    from neo4j import GraphDatabase

    uri = require_env("NEO4J_BOLT_URL")

    props = [key for _, key in MEDICAL_FIELDS]
    cypher = (
        "MATCH (d:Disease) "
        "RETURN d.name AS name, "
        + ", ".join(f"d.{p} AS {p}" for p in props)
        + " ORDER BY d.name"
    )

    driver = GraphDatabase.driver(
        uri, auth=(require_env("NEO4J_USER"), require_env("NEO4J_PASSWORD"))
    )
    docs = []
    with driver.session() as session:
        for rec in session.run(cypher):
            parts = [f"# {rec['name']}"]
            for label, key in MEDICAL_FIELDS:
                value = (rec[key] or "").strip()
                if value:
                    parts.append(f"【{label}】{value}")
            if len(parts) == 1:      # 除了标题什么都没有，跳过
                continue
            docs.append(
                Document(
                    page_content="\n".join(parts),
                    metadata={"name": rec["name"], "source": "medical-kg"},
                )
            )
    driver.close()
    print(f"从 Neo4j 读取 {len(docs)} 个疾病文档")
    return docs


# 文本分割函数
def split_document(docs: List[Document], chunk_size: int = 300, chunk_overlap: int = 30):
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,   # 每个文本块最大长度
        chunk_overlap=chunk_overlap,  # 相邻文本块的重叠长度
        separators=['\n\n', '\n', ' ', ''],  # 分割优先级
    )
    chunks = splitter.split_documents(docs)
    print(f"切分出 {len(chunks)} 个文本块")
    return chunks


# 向量化一批文本块并返回向量库。
# 被嵌入服务拒绝时（Ollama 的 runner 对超大请求直接回 400/EOF）折半重试，
# 免得一次抖动让整轮 20 分钟的构建白跑。
def _embed_to_index(chunks: List[Document]) -> FAISS:
    try:
        # 参数1：要向量化的文本块；参数2：词嵌入模型
        return FAISS.from_documents(chunks, ollama_embedding)
    except Exception:
        if len(chunks) <= MIN_BATCH_SIZE:
            raise
        half = len(chunks) // 2
        print(f"  本批 {len(chunks)} 条被拒，折半为 {half} 条重试", flush=True)
        left = _embed_to_index(chunks[:half])
        right = _embed_to_index(chunks[half:])
        left.merge_from(right)
        return left


# 向量化并写入向量数据库
def save_document(chunks: List[Document], target: Path = INDEX_PATH, batch_size: int = BATCH_SIZE):
    target = Path(target)
    # 旧索引存在则先删除，避免新旧数据混在一起
    if target.exists():
        shutil.rmtree(target)
        print("删除原数据成功")

    # 分批向量化：FAISS.from_documents 会把整批文本一次性发给嵌入模型，
    # 语料一大（本项目医疗语料近 3 万个文本块）就会压垮请求。
    # 这里按 batch_size 切分，逐批建索引再合并。
    total = len(chunks)
    vectorstore = None
    for start in range(0, total, batch_size):
        vs = _embed_to_index(chunks[start:start + batch_size])
        if vectorstore is None:
            vectorstore = vs
        else:
            vectorstore.merge_from(vs)
        print(f"  已向量化 {min(start + batch_size, total)}/{total}", flush=True)

    vectorstore.save_local(str(target))
    print(f"向量库已保存到 {target}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("source", nargs="?", default="springboot",
                        choices=["springboot", "medical"])
    parser.add_argument("--chunk-size", type=int, default=None)
    parser.add_argument("--chunk-overlap", type=int, default=None)
    args = parser.parse_args()

    if args.source == "medical":
        chunks = split_document(
            load_medical_documents(),
            chunk_size=args.chunk_size or 500,
            chunk_overlap=args.chunk_overlap or 50,
        )
        save_document(chunks, MEDICAL_INDEX_PATH)
    else:
        chunks = split_document(
            load_document(),
            chunk_size=args.chunk_size or 300,
            chunk_overlap=args.chunk_overlap or 30,
        )
        save_document(chunks, INDEX_PATH)
