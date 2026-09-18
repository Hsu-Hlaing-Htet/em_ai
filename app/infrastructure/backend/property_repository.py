"""Adapter: reads property data from the backend's public endpoints.

Endpoints:
    GET /public/properties
    GET /public/properties/{id}

Laravel wraps lists as ``{"data": [...], "meta": {...}}``.
"""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from app.domain.models import Property
from app.infrastructure.backend.client import BackendClient, BackendError


def normalize_properties_payload(payload: Any) -> list[Any]:
    """Normalize Laravel public property JSON into a list of property dicts."""
    if payload is None:
        return []
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        data = payload.get("data", [])
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return [data]
        return []
    return []


def normalize_property_payload(payload: Any) -> dict[str, Any] | None:
    if payload is None:
        return None
    if isinstance(payload, dict) and "data" in payload and isinstance(payload["data"], dict):
        return payload["data"]
    if isinstance(payload, dict):
        return payload
    return None


def _unwrap(payload: Any) -> Any:
    """Compatibility helper for rent repository nested ``data`` envelopes."""
    while isinstance(payload, dict) and "data" in payload:
        inner = payload["data"]
        # Stop before unwrapping list items that happen to be dicts with "data"
        if isinstance(inner, list):
            return inner
        payload = inner
    return payload


class BackendPropertyRepository:
    def __init__(self, client: BackendClient) -> None:
        self._client = client

    async def list_properties(
        self, *, query: str | None = None, purpose: str | None = None
    ) -> list[Property]:
        params: dict[str, str | int] = {"per_page": 24}
        if query:
            params["search"] = query
        if purpose in {"rent", "sale"}:
            params["purpose"] = purpose

        payload = await self._client.get_json("/public/properties", params=params)
        items = normalize_properties_payload(payload)

        # #region agent log
        try:
            import json as _json
            import time as _time

            with open(
                "/Users/hsuhtet/rosewood/.cursor/debug-cc4b96.log", "a", encoding="utf-8"
            ) as _f:
                _f.write(
                    _json.dumps(
                        {
                            "sessionId": "cc4b96",
                            "runId": "post-fix",
                            "hypothesisId": "A,B",
                            "location": "property_repository.py:list_properties",
                            "message": "Laravel properties fetched",
                            "data": {"params": params, "count": len(items)},
                            "timestamp": int(_time.time() * 1000),
                        }
                    )
                    + "\n"
                )
        except Exception:
            pass
        # #endregion

        properties: list[Property] = []
        for item in items:
            try:
                properties.append(Property.model_validate(item))
            except ValidationError as exc:
                raise BackendError(
                    f"property schema validation failed: {exc}",
                    kind="validation",
                ) from exc
        return properties

    async def get_property(self, property_id: int) -> Property | None:
        payload = await self._client.get_json(f"/public/properties/{property_id}")
        data = normalize_property_payload(payload)
        if data is None:
            return None
        try:
            return Property.model_validate(data)
        except ValidationError as exc:
            raise BackendError(
                f"property schema validation failed for id={property_id}: {exc}",
                kind="validation",
            ) from exc
