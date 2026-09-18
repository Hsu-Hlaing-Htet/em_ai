"""Aggregates the v1 routes under a single router."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.routes import property, rent

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(property.router)
api_router.include_router(rent.router)
