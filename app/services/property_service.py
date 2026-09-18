"""Use case: answer a question about properties, grounded in backend data."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.core.logging import get_logger
from app.domain.models import Property
from app.domain.ports import PropertyDataSource
from app.llm.chains import build_property_chain
from app.services.context import to_context

logger = get_logger(__name__)

_BEDROOM_RE = re.compile(
    r"\b(\d+)\s*(?:bed(?:room)?s?|br)\b",
    re.IGNORECASE,
)
_LOCATION_RE = re.compile(
    r"\b(?:in|near|around|at)\s+([A-Za-z][A-Za-z\s]{1,40}?)(?:\s+township)?\b",
    re.IGNORECASE,
)
_AMENITY_KEYWORDS = {
    "Parking": ("parking", "garage", "car park"),
    "Garden": ("garden", "yard", "lawn"),
    "Swimming Pool": ("pool", "swimming"),
    "Security": ("security", "cctv", "guard"),
}


@dataclass
class PropertyAnswer:
    answer: str
    properties: list[Property]


@dataclass
class _SearchIntent:
    purpose: str | None = None
    bedrooms: int | None = None
    location: str | None = None
    amenities: list[str] | None = None
    search_query: str | None = None


class PropertyService:
    def __init__(self, data_source: PropertyDataSource) -> None:
        self._data_source = data_source
        self._chain = build_property_chain()

    async def answer(
        self,
        *,
        question: str,
        property_id: int | None = None,
        purpose: str | None = None,
        properties: list[Property] | None = None,
    ) -> PropertyAnswer:
        """Answer ``question``.

        Prefer preloaded ``properties`` from Laravel when provided (proxy path).
        Otherwise fetch from the Laravel public API (direct FastAPI callers).
        """
        intent = self._extract_intent(question, purpose)

        if properties is not None:
            grounded = list(properties)
            if property_id is not None:
                grounded = [item for item in grounded if item.id == property_id]
            grounded = self._apply_intent_filters(grounded, intent)
            fetched_count = len(properties)
        elif property_id is not None:
            prop = await self._data_source.get_property(property_id)
            grounded = [prop] if prop else []
            fetched_count = len(grounded)
        else:
            grounded = await self._data_source.list_properties(
                query=intent.search_query,
                purpose=intent.purpose,
            )
            fetched_count = len(grounded)
            grounded = self._apply_intent_filters(grounded, intent)

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
                            "hypothesisId": "B,C",
                            "location": "property_service.py:answer",
                            "message": "Property search intent and counts",
                            "data": {
                                "purpose": intent.purpose,
                                "search_query": intent.search_query,
                                "bedrooms": intent.bedrooms,
                                "location": intent.location,
                                "amenities": intent.amenities,
                                "preloaded": properties is not None,
                                "fetchedCount": fetched_count,
                                "afterFilterCount": len(grounded),
                            },
                            "timestamp": int(_time.time() * 1000),
                        }
                    )
                    + "\n"
                )
        except Exception:
            pass
        # #endregion

        context = to_context("PROPERTIES", grounded)

        if self._chain is not None:
            try:
                answer = await self._chain.ainvoke(
                    {"context": context, "question": question}
                )
            except Exception as exc:
                logger.warning(
                    "LLM chain failed: %s; falling back to grounded formatter", exc
                )
                answer = self._fallback_answer(question, grounded)
        else:
            answer = self._fallback_answer(question, grounded)

        return PropertyAnswer(answer=answer, properties=grounded)

    def _extract_intent(self, question: str, purpose: str | None) -> _SearchIntent:
        lowered = question.lower()
        resolved_purpose = purpose
        if any(token in lowered for token in ("rent", "rental", "lease", "monthly")):
            resolved_purpose = "rent"
        elif any(token in lowered for token in ("sale", "buy", "purchase", "for sale")):
            resolved_purpose = "sale"

        bedrooms = None
        bedroom_match = _BEDROOM_RE.search(question)
        if bedroom_match:
            bedrooms = int(bedroom_match.group(1))

        location = None
        location_match = _LOCATION_RE.search(question)
        if location_match:
            candidate = location_match.group(1).strip(" .,")
            stopwords = {
                "a",
                "an",
                "the",
                "my",
                "our",
                "yangon",
                "house",
                "home",
                "condo",
                "apartment",
                "villa",
                "property",
                "properties",
            }
            if candidate.lower() not in stopwords and len(candidate) >= 3:
                location = candidate

        amenities: list[str] = []
        for label, keywords in _AMENITY_KEYWORDS.items():
            if any(keyword in lowered for keyword in keywords):
                amenities.append(label)

        # Prefer a focused search string for Laravel LIKE filters.
        search_parts: list[str] = []
        if location:
            search_parts.append(location)
        elif "yangon" in lowered:
            search_parts.append("Yangon")

        search_query = " ".join(search_parts) if search_parts else None

        return _SearchIntent(
            purpose=resolved_purpose,
            bedrooms=bedrooms,
            location=location,
            amenities=amenities or None,
            search_query=search_query,
        )

    def _apply_intent_filters(
        self, properties: list[Property], intent: _SearchIntent
    ) -> list[Property]:
        filtered = properties

        if intent.bedrooms is not None:
            filtered = [
                item
                for item in filtered
                if item.bedrooms is not None and item.bedrooms >= intent.bedrooms
            ]

        if intent.location:
            needle = intent.location.lower()
            location_filtered = [
                item
                for item in filtered
                if needle
                in " ".join(
                    [
                        item.township or "",
                        item.city or "",
                        item.address or "",
                        item.building_location or "",
                        item.property_name or "",
                    ]
                ).lower()
            ]
            if location_filtered:
                filtered = location_filtered

        if intent.amenities:
            amenity_filtered = []
            for item in filtered:
                haystack = " ".join(
                    [
                        *(item.amenities or []),
                        item.description or "",
                    ]
                ).lower()
                if all(amenity.lower() in haystack for amenity in intent.amenities):
                    amenity_filtered.append(item)
            if amenity_filtered:
                filtered = amenity_filtered

        return filtered

    def _fallback_answer(self, question: str, properties: list[Property]) -> str:
        if not properties:
            return (
                "No matching rental properties were found."
                if "rent" in question.lower() or "rental" in question.lower()
                else "No matching Rosewood Royale properties were found for that request. "
                "Could you share preferred bedrooms, budget, and township so I can refine the search?"
            )

        lines = [
            f"I found {len(properties)} Rosewood Royale listing"
            f"{'s' if len(properties) != 1 else ''} that may suit you:\n"
        ]
        for prop in properties[:5]:
            title = prop.property_name or f"Unit {prop.room_number}"
            location = ", ".join(
                part for part in [prop.township, prop.city] if part
            ) or (prop.address or "Rosewood Royale")
            price = None
            if prop.monthly_rent or prop.rent_price:
                amount = prop.monthly_rent or prop.rent_price
                price = f"MMK {amount:,.0f}/month"
            elif prop.sale_price:
                price = f"MMK {prop.sale_price:,.0f}"

            lines.append(f"• {title} — {location}")
            detail_bits = []
            if prop.bedrooms:
                detail_bits.append(f"{prop.bedrooms} bed")
            if prop.bathrooms:
                detail_bits.append(f"{prop.bathrooms} bath")
            if prop.area_sqft:
                detail_bits.append(f"{prop.area_sqft:g} sqft")
            if price:
                detail_bits.append(price)
            if detail_bits:
                lines.append(f"  {' · '.join(detail_bits)}")

        lines.append(
            "\nWould you like more detail on any residence, or shall I refine by bedrooms, budget, or area?"
        )
        return "\n".join(lines)
