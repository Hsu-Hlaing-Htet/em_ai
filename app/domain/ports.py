"""Ports (interfaces) the application depends on.

Services depend on these Protocols, not on concrete HTTP adapters, so the data
source (Laravel API today, a cache or another service tomorrow) can be swapped
without touching business logic. Adapters live in ``app/infrastructure``.
"""

from __future__ import annotations

from typing import Protocol

from app.domain.models import Property, RentProfile


class PropertyDataSource(Protocol):
    async def list_properties(
        self, *, query: str | None = None, purpose: str | None = None
    ) -> list[Property]:
        """Return public properties, optionally filtered by a search query."""
        ...

    async def get_property(self, property_id: int) -> Property | None:
        """Return a single public property, or ``None`` if it does not exist."""
        ...


class RentDataSource(Protocol):
    async def get_rent_profile(self, *, auth_token: str) -> RentProfile:
        """Return the authenticated owner's rent picture (invoices, payments, ...).

        ``auth_token`` is the end user's bearer token, forwarded to the backend
        so its existing authorization rules apply.
        """
        ...
