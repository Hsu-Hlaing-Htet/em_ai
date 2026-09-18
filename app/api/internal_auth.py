"""Optional shared-secret gate for server-to-server calls from Laravel."""

from __future__ import annotations

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse, Response

from app.core.config import settings


class InternalServiceAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        expected = settings.ai_internal_key
        if not expected:
            return await call_next(request)

        if request.url.path in {"/health", "/docs", "/openapi.json", "/redoc"}:
            return await call_next(request)

        provided = request.headers.get("x-rosewood-ai-internal-key", "")
        if provided != expected:
            return JSONResponse(
                status_code=403,
                content={"detail": "Forbidden."},
            )

        return await call_next(request)
