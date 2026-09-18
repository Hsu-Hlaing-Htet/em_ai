"""Thin async HTTP client around the Laravel backend.

One shared ``httpx.AsyncClient`` is created at app startup and reused for every
request (connection pooling). Repositories receive this client via DI rather
than constructing their own.
"""

from __future__ import annotations

import traceback
from typing import Any
from urllib.parse import urljoin

import httpx

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class BackendError(RuntimeError):
    """Raised when the backend returns an error or is unreachable."""

    def __init__(self, message: str, *, kind: str = "connection") -> None:
        super().__init__(message)
        self.kind = kind  # connection | http | json | validation


class BackendClient:
    def __init__(self, http: httpx.AsyncClient) -> None:
        self._http = http

    async def get_json(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        auth_token: str | None = None,
    ) -> Any:
        """GET ``path`` and return the decoded JSON body.

        Returns ``None`` on 404 so callers can treat "not found" as a normal,
        non-exceptional outcome. Other non-2xx responses raise ``BackendError``.
        """
        headers = {"Accept": "application/json"}
        if auth_token:
            headers["Authorization"] = f"Bearer {auth_token}"

        base = str(self._http.base_url)
        final_url = urljoin(base if base.endswith("/") else base + "/", path.lstrip("/"))
        if params:
            logger.info(
                "backend GET base=%s path=%s final_url=%s params=%s",
                base,
                path,
                final_url,
                params,
            )
        else:
            logger.info("backend GET base=%s path=%s final_url=%s", base, path, final_url)

        try:
            response = await self._http.get(path, params=params, headers=headers)
        except httpx.TimeoutException as exc:
            logger.error(
                "backend timeout GET %s final_url=%s exc_type=%s repr=%r traceback=%s",
                path,
                final_url,
                type(exc).__name__,
                exc,
                traceback.format_exc(),
            )
            raise BackendError(
                f"backend timeout calling {final_url}: {type(exc).__name__}: {exc!r}",
                kind="connection",
            ) from exc
        except httpx.HTTPError as exc:
            logger.error(
                "backend request failed GET %s final_url=%s exc_type=%s repr=%r traceback=%s",
                path,
                final_url,
                type(exc).__name__,
                exc,
                traceback.format_exc(),
            )
            raise BackendError(
                f"backend unreachable calling {final_url}: {type(exc).__name__}: {exc!r}",
                kind="connection",
            ) from exc

        content_type = response.headers.get("content-type", "")
        logger.info(
            "backend response GET %s status=%s content_type=%s body_preview=%s",
            path,
            response.status_code,
            content_type,
            response.text[:300],
        )

        if response.status_code == httpx.codes.NOT_FOUND:
            return None
        if response.is_error:
            raise BackendError(
                f"backend returned {response.status_code} for {path}: {response.text[:300]}",
                kind="http",
            )

        try:
            return response.json()
        except ValueError as exc:
            raise BackendError(
                f"backend returned invalid JSON for {path}: {exc!r}",
                kind="json",
            ) from exc


def create_http_client() -> httpx.AsyncClient:
    """Factory for the shared client; wired into the FastAPI lifespan.

    ``trust_env=False`` ignores HTTP(S)_PROXY from the process environment so
    local Laravel calls are not accidentally routed through a broken proxy.
    """
    return httpx.AsyncClient(
        base_url=settings.backend_base_url,
        timeout=settings.backend_timeout_seconds,
        trust_env=False,
    )
