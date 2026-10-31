from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from loguru import logger


class BizException(Exception):
    """业务异常。

    约定：业务错误不抛 HTTP 4xx/5xx，而是返回 HTTP 200，
    在响应体里用 code 字段表示业务状态码。
    """

    def __init__(self, message: str = "业务异常", code: int = 400):
        self.message = message
        self.code = code
        super().__init__(message)


def register_exception_handlers(app: FastAPI) -> None:
    """注册全局异常处理器"""

    @app.exception_handler(BizException)
    async def biz_exception_handler(request: Request, exc: BizException):
        """业务异常 → 返回统一格式，HTTP 状态码固定 200"""
        logger.warning(
            "业务异常 | path={} | code={} | message={}",
            request.url.path,
            exc.code,
            exc.message,
        )
        return JSONResponse(
            status_code=200,
            content={
                "code": exc.code,
                "message": exc.message,
                "data": None,
            },
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        """未捕获的系统异常 → 返回 500 风格的业务码，避免把堆栈暴露给前端"""
        logger.exception(
            "系统异常 | path={} | error={}",
            request.url.path,
            str(exc),
        )
        return JSONResponse(
            status_code=200,
            content={
                "code": 500,
                "message": "服务器内部错误",
                "data": None,
            },
        )