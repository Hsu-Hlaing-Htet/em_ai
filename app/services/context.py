"""Helpers to render domain entities into compact JSON context for the LLM."""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel


def to_context(label: str, data: Any) -> str:
    """Serialise ``data`` (models, lists, dicts) into a labelled JSON block."""

    def encode(value: Any) -> Any:
        if isinstance(value, BaseModel):
            return value.model_dump(exclude_none=True)
        if isinstance(value, list):
            return [encode(item) for item in value]
        if isinstance(value, dict):
            return {k: encode(v) for k, v in value.items()}
        return value

    return f"{label}:\n{json.dumps(encode(data), ensure_ascii=False, indent=2)}"
