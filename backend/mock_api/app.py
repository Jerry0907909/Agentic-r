"""Standalone FastAPI application for dependency-free frontend development."""

from __future__ import annotations

from pathlib import Path
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Allow ``python -m mock_api`` and direct imports from the backend directory.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from api.errors import register_exception_handlers
from mock_api.router import router

app = FastAPI(
    title="Agentic RAG Mock API",
    description="用于前端开发的进程内 Mock 服务，不连接外部数据库或模型服务。",
    version="1.0.0-mock",
)

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
app.include_router(router, prefix="/api", tags=["Mock API"])


@app.get("/", include_in_schema=False)
def index():
    return {"service": "Agentic RAG Mock API", "docs": "/docs"}


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
