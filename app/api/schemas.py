"""Request/response models for the public API surface."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.domain.models import Property, RentProfile


class PropertyQuestionRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    property_id: int | None = Field(
        default=None,
        description="Ground the answer in one property; omit to search listings.",
    )
    purpose: Literal["rent", "sale"] | None = Field(
        default=None,
        description="Filter public listings by rent or sale inventory.",
    )
    properties: list[Property] | None = Field(
        default=None,
        description=(
            "Optional preloaded listings from Laravel. When provided, FastAPI "
            "grounds answers on these and does not call Laravel again "
            "(avoids proxy re-entrancy on single-worker PHP servers)."
        ),
    )


class PropertyQuestionResponse(BaseModel):
    answer: str
    properties: list[Property]
    model: str


class RentQuestionRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    profile: RentProfile | None = Field(
        default=None,
        description=(
            "Optional preloaded authenticated customer context from Laravel. "
            "When provided, FastAPI grounds answers on this and does not call "
            "Laravel again (avoids proxy re-entrancy on single-worker PHP servers)."
        ),
    )


class RentQuestionResponse(BaseModel):
    answer: str
    profile: RentProfile
    model: str
