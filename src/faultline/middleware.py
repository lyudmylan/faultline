"""Request pipeline: correlation id, chaos injection, access log, metrics, 500 envelope."""

import asyncio
import logging
import random
import secrets
import time

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from faultline import chaos, metrics
from faultline.logging_setup import request_id_var

logger = logging.getLogger("faultline.request")


class RequestPipelineMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get("X-Request-ID") or secrets.token_hex(6)
        token = request_id_var.set(request_id)
        start = time.perf_counter()
        status = 500
        try:
            response = await self._handle(request, call_next, request_id)
            status = response.status_code
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            duration_ms = (time.perf_counter() - start) * 1000
            route = request.scope.get("route")
            path_label = route.path_format if route is not None else request.url.path
            client = f"{request.client.host}:{request.client.port}" if request.client else None
            logger.info(
                "%s %s -> %s",
                request.method,
                request.url.path,
                status,
                extra={
                    "event": "request",
                    "method": request.method,
                    "path": request.url.path,
                    "status": status,
                    "duration_ms": round(duration_ms, 3),
                    "client": client,
                },
            )
            metrics.observe_request(request.method, path_label, status, duration_ms / 1000)
            request_id_var.reset(token)

    async def _handle(
        self, request: Request, call_next: RequestResponseEndpoint, request_id: str
    ) -> Response:
        if chaos.state.enabled and not chaos.is_exempt(request.url.path):
            if chaos.state.extra_latency_ms > 0:
                await asyncio.sleep(random.uniform(0, chaos.state.extra_latency_ms) / 1000)
            if random.random() < chaos.state.failure_rate:
                logger.warning(
                    "chaos-injected failure",
                    extra={
                        "event": "chaos_failure",
                        "method": request.method,
                        "path": request.url.path,
                    },
                )
                return JSONResponse(
                    {"error": "service temporarily degraded", "request_id": request_id},
                    status_code=chaos.state.error_status,
                )
        try:
            return await call_next(request)
        except Exception as exc:
            exception_type = type(exc).__name__
            metrics.observe_exception(exception_type)
            logger.error(
                "unhandled exception: %s",
                exc,
                exc_info=exc,
                extra={"event": "unhandled_exception", "exception_type": exception_type},
            )
            return JSONResponse(
                {
                    "error": "internal server error",
                    "exception_type": exception_type,
                    "request_id": request_id,
                },
                status_code=500,
            )
