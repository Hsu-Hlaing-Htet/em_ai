"""Adapter: reads the authenticated customer's portal data from the backend.

Endpoints mirror the Laravel customer portal API (Bearer token forwarded):
    GET /customer/dashboard
    GET /customer/profile
    GET /customer/contracts
    GET /customer/invoices
    GET /customer/payments
    GET /customer/receipts
    GET /customer/maintenance-requests
    GET /customer/notifications

Fetched concurrently; individual failures are tolerated so one missing
endpoint never sinks the whole answer. Customer isolation is enforced by
Laravel authorization — this adapter only uses the caller's token.
"""

from __future__ import annotations

import asyncio
from typing import Any

from app.core.logging import get_logger
from app.domain.models import (
    Contract,
    Invoice,
    MaintenanceRequest,
    Notification,
    Payment,
    Profile,
    Receipt,
    RentProfile,
)
from app.infrastructure.backend.client import BackendClient, BackendError
from app.infrastructure.backend.property_repository import _unwrap
from app.services.privacy import sanitize_for_customer

logger = get_logger(__name__)

_LIST_PARAMS = {"per_page": 100}


class BackendRentRepository:
    def __init__(self, client: BackendClient) -> None:
        self._client = client

    async def get_rent_profile(self, *, auth_token: str) -> RentProfile:
        (
            dashboard,
            profile,
            contracts,
            invoices,
            payments,
            receipts,
            maintenance,
            notifications,
        ) = await asyncio.gather(
            self._safe_get("/customer/dashboard", auth_token),
            self._safe_get("/customer/profile", auth_token),
            self._safe_get("/customer/contracts", auth_token, params=_LIST_PARAMS),
            self._safe_get("/customer/invoices", auth_token, params=_LIST_PARAMS),
            self._safe_get("/customer/payments", auth_token, params=_LIST_PARAMS),
            self._safe_get("/customer/receipts", auth_token, params=_LIST_PARAMS),
            self._safe_get("/customer/maintenance-requests", auth_token, params=_LIST_PARAMS),
            self._safe_get("/customer/notifications", auth_token),
        )

        contract_models = _as_list(contracts, Contract)
        invoice_models = _as_list(invoices, Invoice)
        payment_models = _as_list(payments, Payment)
        receipt_models = _as_list(receipts, Receipt)
        maintenance_models = _as_list(maintenance, MaintenanceRequest)
        notification_models = _as_notification_list(notifications)
        profile_model = _as_profile(profile)
        dashboard_data = _unwrap(dashboard)
        if not isinstance(dashboard_data, dict):
            dashboard_data = None

        documents = _build_documents(
            contracts=contract_models,
            invoices=invoice_models,
            receipts=receipt_models,
        )

        return RentProfile(
            dashboard=sanitize_for_customer(dashboard_data),
            profile=sanitize_for_customer(
                profile_model.model_dump(exclude_none=True) if profile_model else None
            ),
            contracts=_sanitize_models(contract_models),
            invoices=_sanitize_models(invoice_models),
            payments=_sanitize_models(payment_models),
            receipts=_sanitize_models(receipt_models),
            maintenance_requests=_sanitize_models(maintenance_models),
            notifications=_sanitize_models(notification_models),
            documents=sanitize_for_customer(documents),
        )

    async def _safe_get(
        self,
        path: str,
        auth_token: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> Any:
        try:
            return await self._client.get_json(path, params=params, auth_token=auth_token)
        except BackendError:
            logger.info("rent source %s unavailable; continuing without it", path)
            return None


def _as_list(payload: Any, model: type) -> list:
    items = _unwrap(payload) or []
    if not isinstance(items, list):
        return []
    return [model.model_validate(sanitize_for_customer(item)) for item in items]


def _as_notification_list(payload: Any) -> list[Notification]:
    items = _unwrap(payload) or []
    if not isinstance(items, list):
        return []
    return [Notification.model_validate(sanitize_for_customer(item)) for item in items]


def _as_profile(payload: Any) -> Profile | None:
    data = _unwrap(payload)
    if not isinstance(data, dict):
        return None
    return Profile.model_validate(sanitize_for_customer(data))


def _sanitize_models(models: list) -> list:
    cleaned = []
    for model in models:
        payload = sanitize_for_customer(model.model_dump(exclude_none=True))
        cleaned.append(type(model).model_validate(payload))
    return cleaned


def _invoice_is_utility(invoice: Invoice) -> bool:
    kind = (invoice.invoice_type or invoice.type or "").lower()
    return kind == "utility"


def _build_documents(
    *,
    contracts: list[Contract],
    invoices: list[Invoice],
    receipts: list[Receipt],
) -> dict[str, Any]:
    """Document availability derived from records the customer can already open."""
    utility_invoices = [inv for inv in invoices if _invoice_is_utility(inv)]
    return {
        "contract_documents": [
            {
                "contract_number": c.contract_number or c.id,
                "status": c.status,
                "available": True,
            }
            for c in contracts
        ],
        "invoice_documents": [
            {
                "invoice_number": inv.invoice_number or inv.id,
                "type": inv.invoice_type or inv.type,
                "status": inv.status,
                "available": True,
            }
            for inv in invoices
        ],
        "receipt_documents": [
            {
                "receipt_number": r.receipt_number or r.id,
                "status": r.display_status or r.status,
                "available": True,
            }
            for r in receipts
        ],
        "utility_bill_documents": [
            {
                "invoice_number": inv.invoice_number or inv.id,
                "billing_period": inv.billing_period or inv.billing_month,
                "status": inv.status,
                "available": True,
            }
            for inv in utility_invoices
        ],
    }
