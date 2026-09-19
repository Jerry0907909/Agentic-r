"""Ollama 模型配置：本地大模型 + 词嵌入模型"""

from langchain_ollama import ChatOllama, OllamaEmbeddings

# .env 由 utils.paths 统一加载（全项目唯一加载点），import 本模块时已就绪：
# 这里不再自己 load_dotenv，取值也就不再依赖「谁先被 import」。
from backend.utils.paths import require_env

# 关键修复：httpx 默认读取 macOS 系统代理（127.0.0.1:9674），
# 会把发往本地 Ollama 的请求转给代理，导致 502。必须关闭 trust_env。
CLIENT_KWARGS = {"trust_env": False}

# 初始化大模型
ollama_model = ChatOllama(
    model=require_env("OLLAMA_LLM"),
    temperature=0.3,
    client_kwargs=CLIENT_KWARGS,
)

# 初始化词嵌入模型
ollama_embedding = OllamaEmbeddings(
    model=require_env("OLLAMA_EMBEDDING"),
    client_kwargs=CLIENT_KWARGS,
)
