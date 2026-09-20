"""接口层：应用装配。

只做装配 —— 建 FastAPI 实例、挂中间件、注册路由、管生命周期。
业务逻辑一律不写在这里（见 系统设计.md §1.2 的分层职责表）。

启动：
    cd backend && uvicorn api.chat_api:app --reload --port 8000
    文档：http://127.0.0.1:8000/docs
"""

from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

# 项目根加入模块搜索路径（唯一自举语句，说明见 utils/paths.py）
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from api.errors import register_exception_handlers
from api.routers import ask, conversation, system
from db.session import engine, init_db
from utils.paths import PROJECT_ROOT

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
)
logger = logging.getLogger("api")

# 演示期单端口部署用：前端构建产物在 backend/ 的**兄弟目录**下。
# 不能写成相对路径 "frontend/dist" —— 那会解析成 backend/frontend/dist（不存在）。
# 这里与全项目「路径由 utils/paths.py 统一推导」的约定保持一致，用 PROJECT_ROOT 算绝对路径。
FRONTEND_DIST = PROJECT_ROOT.parent / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动时初始化资源，关闭时释放。取代已废弃的 @app.on_event。"""
    # 建库建表（幂等）。这样「先起服务、后想起建表」不会变成一个静默失败：
    # 没有这一步，第一次问答会在写库时抛外键/表不存在错误。
    init_db()
    logger.info("数据库就绪，接口文档：http://127.0.0.1:8000/docs")
    yield
    engine.dispose()
    logger.info("数据库连接池已释放")


app = FastAPI(
    title="Agentic RAG 医疗智能问答系统",
    description=(
        "基于 LangGraph 的医疗领域 Agentic RAG 服务。\n\n"
        "**接口分三层**：L1 问答域（NDJSON 流式）/ L2 会话域 / L3 系统域。\n\n"
        "流式协议的事件顺序为 `sid? → c c c … c → s? → u?`，"
        "详见《接口文档》§3.4。\n\n"
        "> 本系统仅用于课程演示，不构成医疗建议。"
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# 开发期前端跑在 5173、后端在 8000，属于跨域。
# 推荐用 Vite 代理（见 接口文档.md §1.6），这里是作为兜底 ——
# 例如直接用 file:// 打开 HTML 调试时。
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "http://127.0.0.1:8000",
        "http://localhost:8000",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)

# 三层路由，与功能层级一一对应；tags 会体现在 /docs 的分组上
app.include_router(ask.router, prefix="/api", tags=["L1 问答域"])
app.include_router(conversation.router, prefix="/api", tags=["L2 会话域"])
app.include_router(system.router, prefix="/api", tags=["L3 系统域"])


if FRONTEND_DIST.exists():
    # 必须放在最后注册：Starlette 按注册顺序匹配，先注册的 /api/* 会优先命中，
    # 挂在 "/" 上的静态目录只兜底其余路径。
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="frontend")
    logger.info("已挂载前端构建产物：%s", FRONTEND_DIST)
else:
    @app.get("/", include_in_schema=False)
    def _index():
        """前端还没构建时的占位提示，避免访问根路径看到裸 404。"""
        return JSONResponse({
            "service": "Agentic RAG 医疗智能问答系统",
            "docs": "/docs",
            "note": "前端尚未构建。开发期请 cd frontend && npm run dev；"
                    "演示期请先 npm run build 再重启本服务。",
        })


# ── OpenAPI 后处理 ──────────────────────────────────────────────────────────
# 流式端点为了把 StreamEvent / Source / Usage 注册进 components.schemas，
# 声明了 `"model": StreamEvent`（见 api/routers/ask.py）。FastAPI 会因此在
# 该响应的 content 里额外补一条 `application/json` —— 但这两个端点是**纯
# NDJSON 流**，`/docs` 上出现 application/json 会让人以为可以按普通 JSON 调。
# 这里把这条多余条目摘掉，既保住类型生成，又让文档如实反映协议。
def _custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    from fastapi.openapi.utils import get_openapi

    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
        tags=app.openapi_tags,
    )
    for operations in schema.get("paths", {}).values():
        for operation in operations.values():
            for response in (operation.get("responses") or {}).values():
                content = response.get("content") or {}
                if "application/x-ndjson" in content and "application/json" in content:
                    content.pop("application/json")

    app.openapi_schema = schema
    return schema


app.openapi = _custom_openapi


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("api.chat_api:app", host="127.0.0.1", port=8000, reload=True)
