"""Adapter: reads the authenticated customer's rent data from the backend.

Endpoints mirror the Laravel customer portal API:
    GET /customer/dashboard
    GET /customer/contracts
    GET /customer/invoices
    GET /customer/payments

All four are fetched concurrently and tolerate individual failures so a single
missing endpoint never sinks the whole answer.
"""

from __future__ import annotations

import asyncio
from typing import Any

from app.core.logging import get_logger
from app.domain.models import Contract, Invoice, Payment, RentProfile
from app.infrastructure.backend.client import BackendClient, BackendError
from app.infrastructure.backend.property_repository import _unwrap

logger = get_logger(__name__)


class BackendRentRepository:
    def __init__(self, client: BackendClient) -> None:
        self._client = client

    async def get_rent_profile(self, *, auth_token: str) -> RentProfile:
        dashboard, contracts, invoices, payments = await asyncio.gather(
            self._safe_get("/customer/dashboard", auth_token),
            self._safe_get("/customer/contracts", auth_token),
            self._safe_get("/customer/invoices", auth_token),
            self._safe_get("/customer/payments", auth_token),
        )

        return RentProfile(
            dashboard=_unwrap(dashboard) if isinstance(_unwrap(dashboard), dict) else None,
            contracts=_as_list(contracts, Contract),
            invoices=_as_list(invoices, Invoice),
            payments=_as_list(payments, Payment),
        )

    async def _safe_get(self, path: str, auth_token: str) -> Any:
        try:
            return await self._client.get_json(path, auth_token=auth_token)
        except BackendError:
            logger.info("rent source %s unavailable; continuing without it", path)
            return None


def _as_list(payload: Any, model: type) -> list:
    items = _unwrap(payload) or []
    if not isinstance(items, list):
        return []
    return [model.model_validate(item) for item in items]
