"""接口层：业务异常与统一错误信封。

`BizError` 刻意放在独立模块，而不是像 接口文档.md §7.5 的示例那样写在
`chat_api.py` 里：路由模块需要 `raise BizError(...)`，而 `chat_api.py` 又要
import 路由来注册 —— 放在一起会形成循环导入。独立成模块后依赖是单向的：

    errors.py  ←  routers/*  ←  chat_api.py
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from api.schemas import ErrorBody

logger = logging.getLogger(__name__)

# 业务码 → HTTP 状态码（见 接口文档.md §1.5）
ERROR_HTTP_STATUS = {
    40001: 400,   # 参数缺失或非法
    40401: 404,   # 会话不存在
    50001: 500,   # 向量库不可用（索引缺失）
    50002: 500,   # 图谱不可用（连接或认证失败）
    50003: 502,   # 云端模型不可用（超时 / 额度耗尽）
    50004: 503,   # 重排服务不可用
}


class BizError(Exception):
    """业务异常。`code` 见 接口文档.md §1.5。

    注意 50004（重排不可用）**不应被抛出** —— 重排失败要静默降级为 RRF 结果，
    链路继续走完。这个码只用于日志，不进响应（见 接口文档.md §1.5）。
    """

    def __init__(self, code: int, msg: str, detail: str | None = None):
        super().__init__(msg)
        self.code = code
        self.msg = msg
        self.detail = detail


# 路由上要显式声明的错误响应。
#
# 为什么必须显式声明：错误信封是通过 JSONResponse 返回的，FastAPI 不会自动把它
# 写进 OpenAPI —— 不声明的话，前端 `npm run api:types` 生成出来的类型里
# **压根没有错误信封**，`unwrap()` 只能靠手写 `{code, msg, detail}` 去断言，
# 契约就断了一截（见 接口文档.md §7.6 关于 response_model 的说明）。
ERROR_RESPONSES = {
    400: {"model": ErrorBody, "description": "参数缺失或非法（40001）"},
    404: {"model": ErrorBody, "description": "会话不存在（40401）"},
    500: {
        "model": ErrorBody,
        "description": "依赖不可用：向量库索引缺失（50001）/ 图谱连接或认证失败（50002）",
    },
    502: {"model": ErrorBody, "description": "云端模型不可用，超时或额度耗尽（50003）"},
}


def _envelope(code: int, msg: str, detail: str | None) -> dict:
    return ErrorBody(code=code, msg=msg, detail=detail).model_dump()


def register_exception_handlers(app: FastAPI) -> None:
    """把三类异常统一成同一种错误信封。"""

    @app.exception_handler(BizError)
    async def _biz(request: Request, exc: BizError):
        return JSONResponse(
            status_code=ERROR_HTTP_STATUS.get(exc.code, 500),
            content=_envelope(exc.code, exc.msg, exc.detail),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError):
        """Pydantic 校验失败 → 40001。

        不接管的话 FastAPI 会返回自己的 `{"detail": [...]}` 结构，
        前端按统一信封解析会拿到 undefined。
        """
        first = exc.errors()[0] if exc.errors() else {}
        loc = ".".join(str(p) for p in first.get("loc", []) if p != "body")
        msg = first.get("msg", "参数校验失败")
        return JSONResponse(
            status_code=400,
            content=_envelope(40001, "请求参数不合法", f"{loc}: {msg}" if loc else msg),
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):
        """兜底：未预期的异常也要给出结构化信封，而不是 FastAPI 的裸 500。

        `detail` 带上真实异常类型与原文 —— 这是本项目从 cypher_tool 修复中
        总结的教训：异常被吞成统一的 500 后，「连接失败 / 密码错误 / 语法错误」
        长得一模一样，排查时完全没有线索（见 接口文档.md §1.3）。
        """
        logger.exception("未处理的异常：%s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content=_envelope(50000, "服务器内部错误", f"{type(exc).__name__}: {exc}"),
        )
