"""路径与环境变量的唯一真相源。

本项目里所有「文件在哪」「环境变量从哪来」「用哪个向量库」的问题，
只在本模块回答一次。其余模块一律 `from utils.paths import ...`，
不要再自己写 `Path(__file__).resolve().parents[1]` 或 `load_dotenv(...)`。

为什么单独抽这一个模块：

1. **.env 只在这里加载一次**。以前 cypher_tool 和 ollama_llm 各加载一遍，
   而 rag_tool 取环境变量时靠的是「先 import 了 ollama_llm」这个副作用 ——
   谁挪一下那行 import，它就会静默读到错误的值（或读不到）。
   现在任何模块只要 import utils.paths，.env 就已经加载好了，与 import 顺序无关。

2. **项目根只在这里算一次**。以前全项目混用 `parents[1]` 和 `parent.parent`
   两种写法散落 6 处，改目录结构时得挨个找。

关于「直接运行某个 .py 文件」：
    Python 只把**脚本所在目录**放进 sys.path，项目根不在里面，于是 `tools`、
    `llm`、`utils` 这些顶层包就可能解析到别处的同名副本（本项目就踩过：
    同名副本 agent-rag 抢先被 import，报 `No module named 'tools.cypher_tool'`）。
    入口脚本（带 `if __name__ == "__main__"` 的文件）在**任何本项目 import 之前**
    放这 4 行即可：

        import sys
        from pathlib import Path

        # 项目根加入模块搜索路径（唯一自举语句，说明见 utils/paths.py）
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

    这行没法再集中到函数里 —— 要 import 本模块就得先把项目根放进 sys.path，
    先有鸡才有蛋。所以全项目就这一份写法，各入口照抄，不要变体。
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# 本文件在 <项目根>/utils/paths.py，故 parents[1] 即项目根
PROJECT_ROOT = Path(__file__).resolve().parents[1]

ENV_PATH = PROJECT_ROOT / ".env"
FAISS_INDEX_DIR = PROJECT_ROOT / "faiss-index"

# 唯一的 .env 加载点，override=True 必须加：
# ~/.zshrc 与 ~/.zprofile 会 source ~/.neo4j/aura.env，其中导出的
# NEO4J_PASSWORD / NEO4J_URI 会盖掉本项目 .env 的同名变量。不覆盖的话，
# 脚本会拿 Aura 云实例的密码去连本地 127.0.0.1:7687，认证失败后异常被吞成
# {"code": 500}，排查时完全没有线索。
load_dotenv(ENV_PATH, override=True)


def require_env(key: str) -> str:
    """取环境变量；缺失时立刻报错，并指出 .env 的位置。

    以前是 os.getenv(key) 拿到 None 再往下传，错误在很远的地方才以难以理解的
    方式爆出来（model=None、认证失败等），定位成本很高。
    """
    value = os.getenv(key)
    if not value:
        raise RuntimeError(f"环境变量 {key} 未配置，请检查 {ENV_PATH}")
    return value


# 语料名 -> 索引目录。加新语料只需在这里加一行。
INDEXES = {
    "default": FAISS_INDEX_DIR / "default",   # Spring Boot 语料（课程早期 RAG 示例）
    "medical": FAISS_INDEX_DIR / "medical",   # 医疗语料，由 rag_index.py medical 生成
}

# 语料名 -> 构建该语料时传给 utils/rag_index.py 的参数
INDEX_BUILD_ARGS = {"default": "springboot", "medical": "medical"}

# .env 没指定 FAISS_INDEX_NAME 时用哪个语料。
# 必须是 medical：rag_tool 的工具说明和 rag_agent 的提示词都按「医疗」写的。
# 以前这里没有显式默认值、.env 里也没有这一项，于是静默回退到 default
# （Spring Boot 语料）——模型拿 Spring Boot 的文本回答「百日咳是什么病」，
# 全程不报任何错，是最难查的一类 bug。
DEFAULT_INDEX = "medical"


def index_path(name: str | None = None) -> Path:
    """返回语料对应的索引目录；name 缺省时取 .env 的 FAISS_INDEX_NAME。

    只算路径、不检查是否存在（构建索引时目录本来就不存在）。
    """
    name = name or os.getenv("FAISS_INDEX_NAME") or DEFAULT_INDEX
    if name not in INDEXES:
        raise RuntimeError(
            f"未知的语料名 {name!r}，可选：{', '.join(sorted(INDEXES))}"
            f"（由 .env 的 FAISS_INDEX_NAME 指定）"
        )
    return INDEXES[name]


def require_index(name: str | None = None) -> Path:
    """返回已构建好的索引目录；不存在就报错，并给出构建命令。

    和 index_path 的区别：这里会检查存在性，用于「要读索引」的场景，
    保证缺索引时是明确报错，而不是静默换一个语料。
    """
    resolved = name or os.getenv("FAISS_INDEX_NAME") or DEFAULT_INDEX
    path = index_path(resolved)
    if not path.exists():
        raise FileNotFoundError(
            f"向量库不存在：{path}\n"
            f"请先构建：python utils/rag_index.py {INDEX_BUILD_ARGS.get(resolved, resolved)}"
        )
    return path
