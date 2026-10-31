import time
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from loguru import logger


class LoggingMiddleware(BaseHTTPMiddleware):
    """请求日志中间件：记录每个请求的方法、路径、状态码和耗时。"""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.perf_counter()

        # 获取客户端 IP（兼容代理）
        client_ip = request.client.host if request.client else "-"
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            client_ip = forwarded.split(",")[0].strip()

        try:
            response = await call_next(request)
        except Exception as exc:
            # 异常也会被记录耗时
            process_time = (time.perf_counter() - start_time) * 1000
            logger.error(
                "{method} {path} | {status} | {time:.2f}ms | {ip} | 异常: {error}",
                method=request.method,
                path=request.url.path,
                status=500,
                time=process_time,
                ip=client_ip,
                error=str(exc),
            )
            raise

        process_time = (time.perf_counter() - start_time) * 1000

        # 根据状态码选择日志级别
        if response.status_code >= 500:
            log_func = logger.error
        elif response.status_code >= 400:
            log_func = logger.warning
        else:
            log_func = logger.info

        log_func(
            "{method} {path} | {status} | {time:.2f}ms | {ip}",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            time=process_time,
            ip=client_ip,
        )

        # 把耗时也写进响应头，方便调试
        response.headers["X-Process-Time"] = f"{process_time:.2f}ms"
        return response