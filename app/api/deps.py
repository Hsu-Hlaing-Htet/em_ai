"""Dependency-injection wiring for the API layer.

Constructs the adapter → repository → service graph per request. The shared
``httpx.AsyncClient`` lives on ``app.state`` (set in the lifespan); everything
else is cheap to build per request. Swapping the data source (e.g. to a cached
or mock implementation in tests) means changing only this module.
"""

from __future__ import annotations

from typing import Annotated

import httpx
from fastapi import Depends, Header, HTTPException, Request, status

from app.infrastructure.backend.client import BackendClient
from app.infrastructure.backend.property_repository import BackendPropertyRepository
from app.infrastructure.backend.rent_repository import BackendRentRepository
from app.services.property_service import PropertyService
from app.services.rent_service import RentService


def get_http_client(request: Request) -> httpx.AsyncClient:
    return request.app.state.http_client


def get_backend_client(
    http: Annotated[httpx.AsyncClient, Depends(get_http_client)],
) -> BackendClient:
    return BackendClient(http)


def get_property_service(
    client: Annotated[BackendClient, Depends(get_backend_client)],
) -> PropertyService:
    return PropertyService(BackendPropertyRepository(client))


def get_rent_service(
    client: Annotated[BackendClient, Depends(get_backend_client)],
) -> RentService:
    return RentService(BackendRentRepository(client))


def get_auth_token(
    authorization: Annotated[str | None, Header()] = None,
) -> str:
    """Extract the end user's bearer token; rent answers require it."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return authorization.split(" ", 1)[1].strip()
