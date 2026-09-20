"""模型层 · 本地模型：**只提供词嵌入（Embedding）**。

分工（2026-09-20 调整）：

| 用途 | 模型 | 位置 |
| --- | --- | --- |
| 向量化 / 检索（FAISS 索引 + 查询编码） | 本地 Ollama `nomic-embed-text` | 本模块 |
| 全部问答（rag_agent / cypher_agent） | 云端 DashScope `qwen3-max` | `llm/qwen_llm.py` |

**为什么不再用本地模型做问答**：
1. 本机 `qwen3:4b` 是推理模型，思考阶段客户端收不到任何 chunk，
   经智能体两轮调用叠加，首 token 实测 140s，远不满足非功能需求「本地 4B < 15s」；
2. 更关键的是，同样的检索结果下，云端模型的回答质量明显更稳（结构化、忠实于资料），
   本地 4B 容易答非所问。演示链路不该压在一个能力边缘的模型上。
3. 嵌入模型没有这个问题：`nomic-embed-text` 快、稳、无思考模式，且本地跑省调用费。

保留本地嵌入的意义：索引构建（3 万块向量化）与每次查询的编码都在本机完成，
不产生云端调用成本，也不受网络波动影响。

文件名仍叫 `ollama_llm.py` 是为了少改动（`utils/rag_index.py`、`retrieval/dense.py`
都从这里取 `ollama_embedding`），它现在只导出嵌入模型。
"""

from langchain_ollama import OllamaEmbeddings

# .env 由 utils.paths 统一加载（全项目唯一加载点），import 本模块时已就绪：
# 这里不再自己 load_dotenv，取值也就不再依赖「谁先被 import」。
from utils.paths import require_env

# 关键修复：httpx 默认读取 macOS 系统代理（127.0.0.1:9674），
# 会把发往本地 Ollama 的请求转给代理，导致 502。必须关闭 trust_env。
CLIENT_KWARGS = {"trust_env": False}

# 初始化词嵌入模型（本地 Ollama）
ollama_embedding = OllamaEmbeddings(
    model=require_env("OLLAMA_EMBEDDING"),
    client_kwargs=CLIENT_KWARGS,
)
