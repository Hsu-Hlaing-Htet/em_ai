"""LangChain runnables: prompt | model | string output.

Each chain takes ``{"context": str, "question": str}`` and returns the model's
answer as a string.
"""

from __future__ import annotations

from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import Runnable

from app.llm.client import get_chat_model
from app.llm.prompts import PROPERTY_PROMPT, RENT_PROMPT


def build_property_chain() -> Runnable | None:
    model = get_chat_model()
    if model is None:
        return None
    return PROPERTY_PROMPT | model | StrOutputParser()


def build_rent_chain() -> Runnable | None:
    model = get_chat_model()
    if model is None:
        return None
    return RENT_PROMPT | model | StrOutputParser()
