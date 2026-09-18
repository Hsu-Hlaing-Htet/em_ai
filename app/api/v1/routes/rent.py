"""Endpoint 2 — my rent information (authenticated owner)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_auth_token, get_rent_service
from app.api.schemas import RentQuestionRequest, RentQuestionResponse
from app.core.config import settings
from app.infrastructure.backend.client import BackendError
from app.services.rent_service import RentService

router = APIRouter(prefix="/rent", tags=["rent"])


@router.post("/ask", response_model=RentQuestionResponse)
async def ask_rent(
    payload: RentQuestionRequest,
    service: Annotated[RentService, Depends(get_rent_service)],
    auth_token: Annotated[str, Depends(get_auth_token)],
) -> RentQuestionResponse:
    """Answer a natural-language question about the caller's own rent.

    The caller's ``Authorization: Bearer <token>`` header is forwarded to the
    backend so its existing authorization rules decide what data is visible.
    """
    try:
        result = await service.answer(question=payload.question, auth_token=auth_token)
    except BackendError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Rent data source unavailable: {exc}",
        ) from exc

    return RentQuestionResponse(
        answer=result.answer,
        profile=result.profile,
        model=settings.openai_model,
    )
