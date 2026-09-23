"""Customer-facing context hygiene for the rent assistant.

Strips staff/admin-only fields before data is shown to the LLM, so answers
never leak internal notes or private staff information.
"""

from __future__ import annotations

from typing import Any

CONTACT_FALLBACK = (
    "Please contact our team for assistance.\n"
    "Phone: +95 9 55000001\n"
    "Email: hello@rosewoodroyale.com"
)

# Keys that must never ground a customer-facing answer.
_BLOCKED_KEYS = frozenset(
    {
        "note",
        "notes",
        "internal_note",
        "internal_notes",
        "verification_note",
        "verification_notes",
        "staff_comment",
        "staff_comments",
        "admin_note",
        "admin_notes",
        "approved_by",
        "approved_by_name",
        "created_by",
        "created_by_name",
        "sent_by",
        "sent_by_name",
        "approver",
        "creator",
        "sender",
        "proof_image_path",
        "proof_image_url",
        "avatar_path",
        "password",
        "remember_token",
    }
)

_UNSAFE_PHRASES = (
    "another customer",
    "other customer",
    "someone else's",
    "someone elses",
    "other tenant",
    "another tenant",
    "all customers",
    "every customer",
    "admin note",
    "admin only",
    "internal note",
    "staff comment",
    "staff notes",
    "verification note",
    "debug",
    "system log",
    "database",
)

_MISSING_ANSWER_MARKERS = (
    "data not found",
    "information is unavailable",
    "i couldn't find",
    "i could not find",
    "could not find that",
    "couldn't find that",
    "no information available",
    "not available in the context",
    "context does not contain",
    "context doesn't contain",
    "i don't have that information",
    "i do not have that information",
)


def sanitize_for_customer(value: Any) -> Any:
    """Recursively drop blocked keys from dict/list payloads."""
    if isinstance(value, list):
        return [sanitize_for_customer(item) for item in value]
    if isinstance(value, dict):
        cleaned: dict[str, Any] = {}
        for key, item in value.items():
            if str(key).lower() in _BLOCKED_KEYS:
                continue
            cleaned[key] = sanitize_for_customer(item)
        return cleaned
    return value


def is_out_of_scope_question(question: str) -> bool:
    lowered = (question or "").strip().lower()
    if not lowered:
        return True
    return any(phrase in lowered for phrase in _UNSAFE_PHRASES)


def looks_like_missing_answer(answer: str) -> bool:
    lowered = (answer or "").strip().lower()
    if not lowered:
        return True
    return any(marker in lowered for marker in _MISSING_ANSWER_MARKERS)


def ensure_safe_answer(answer: str) -> str:
    """Replace unsafe / missing-style answers with the contact fallback."""
    text = (answer or "").strip()
    if not text or looks_like_missing_answer(text):
        return CONTACT_FALLBACK
    return text
