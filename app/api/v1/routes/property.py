"""Endpoint 1 — information about a property."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_property_service
from app.api.schemas import PropertyQuestionRequest, PropertyQuestionResponse
from app.core.config import settings
from app.infrastructure.backend.client import BackendError
from app.services.property_service import PropertyService

router = APIRouter(prefix="/property", tags=["property"])


@router.post("/ask", response_model=PropertyQuestionResponse)
async def ask_property(
    payload: PropertyQuestionRequest,
    service: Annotated[PropertyService, Depends(get_property_service)],
) -> PropertyQuestionResponse:
    """Answer a natural-language question about properties.

    Prefer ``properties`` preloaded by Laravel (proxy path). Otherwise FastAPI
    fetches from Laravel itself (direct callers / docs).
    """
    try:
        result = await service.answer(
            question=payload.question,
            property_id=payload.property_id,
            purpose=payload.purpose,
            properties=payload.properties,
        )
    except BackendError as exc:
        status_code = (
            status.HTTP_502_BAD_GATEWAY
            if getattr(exc, "kind", "connection") in {"connection", "http", "json"}
            else status.HTTP_422_UNPROCESSABLE_ENTITY
        )
        raise HTTPException(
            status_code=status_code,
            detail=str(exc),
        ) from exc

    return PropertyQuestionResponse(
        answer=result.answer,
        properties=result.properties,
        model=settings.openai_model,
    )
