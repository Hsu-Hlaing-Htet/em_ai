"""Use case: answer a question about the authenticated customer's portal data."""

from __future__ import annotations

from dataclasses import dataclass

from app.core.logging import get_logger
from app.domain.models import Invoice, RentProfile
from app.domain.ports import RentDataSource
from app.llm.chains import build_rent_chain
from app.services.context import to_context
from app.services.privacy import (
    CONTACT_FALLBACK,
    ensure_safe_answer,
    is_out_of_scope_question,
)

logger = get_logger(__name__)

_UNPAID_STATUSES = frozenset({"issued", "unpaid", "partial", "overdue"})
_ACTIVE_STATUSES = frozenset({"active", "approved"})


@dataclass
class RentAnswer:
    answer: str
    profile: RentProfile


class RentService:
    def __init__(self, data_source: RentDataSource) -> None:
        self._data_source = data_source
        self._chain = build_rent_chain()

    async def answer(
        self,
        *,
        question: str,
        auth_token: str,
        profile: RentProfile | None = None,
    ) -> RentAnswer:
        if is_out_of_scope_question(question):
            resolved = profile or RentProfile()
            if profile is None:
                try:
                    resolved = await self._data_source.get_rent_profile(auth_token=auth_token)
                except Exception:
                    resolved = RentProfile()
            return RentAnswer(answer=CONTACT_FALLBACK, profile=resolved)

        # Prefer Laravel-preloaded profile (proxy path). Fetch only for direct callers.
        if profile is None:
            profile = await self._data_source.get_rent_profile(auth_token=auth_token)

        # Deterministic grounding first for known customer intents — reliable with real data.
        grounded = self._fallback_answer(question, profile)
        if grounded and grounded != CONTACT_FALLBACK:
            if self._chain is None:
                return RentAnswer(answer=grounded, profile=profile)

            # Optional LLM polish only when grounded data exists; never replace with empty fallback.
            context = self._build_context(profile)
            try:
                llm_answer = await self._chain.ainvoke({"context": context, "question": question})
                safe = ensure_safe_answer(llm_answer)
                if safe != CONTACT_FALLBACK:
                    return RentAnswer(answer=safe, profile=profile)
            except Exception as exc:
                logger.warning("LLM chain failed: %s; using grounded formatter", exc)

            return RentAnswer(answer=grounded, profile=profile)

        if self._chain is not None:
            try:
                answer = await self._chain.ainvoke(
                    {"context": self._build_context(profile), "question": question}
                )
                return RentAnswer(answer=ensure_safe_answer(answer), profile=profile)
            except Exception as exc:
                logger.warning("LLM chain failed: %s; falling back to grounded formatter", exc)

        return RentAnswer(answer=grounded or CONTACT_FALLBACK, profile=profile)

    def _build_context(self, profile: RentProfile) -> str:
        return "\n\n".join(
            [
                to_context("PROFILE", profile.profile or {}),
                to_context("DASHBOARD", profile.dashboard or {}),
                to_context("CONTRACTS", profile.contracts),
                to_context("INVOICES", profile.invoices),
                to_context("PAYMENTS", profile.payments),
                to_context("RECEIPTS", profile.receipts),
                to_context("UTILITY_BILLS", _utility_invoices(profile.invoices)),
                to_context("MAINTENANCE_REQUESTS", profile.maintenance_requests),
                to_context("NOTIFICATIONS", profile.notifications),
                to_context("DOCUMENTS", profile.documents or {}),
            ]
        )

    def _fallback_answer(self, question: str, profile: RentProfile) -> str:
        """Deterministic grounded answers from authenticated customer data."""
        q = (question or "").lower()

        if is_out_of_scope_question(question):
            return CONTACT_FALLBACK

        if any(token in q for token in ("email", "profile", "account", "phone", "address", "registered")):
            return self._answer_profile(profile) or CONTACT_FALLBACK

        if any(token in q for token in ("notification", "alert")):
            return self._answer_notifications(profile) or CONTACT_FALLBACK

        if any(token in q for token in ("maintenance", "repair")) or (
            "request" in q and "payment" not in q
        ):
            return self._answer_maintenance(profile) or CONTACT_FALLBACK

        if "receipt" in q:
            return self._answer_receipts(profile) or CONTACT_FALLBACK

        if any(token in q for token in ("utility", "electric", "water", "meter")):
            return self._answer_utilities(profile) or CONTACT_FALLBACK

        if any(token in q for token in ("document", "pdf", "download", "view my contract", "view contract")):
            return self._answer_documents(profile) or CONTACT_FALLBACK

        if any(token in q for token in ("payment", "approved", "rejected", "pending payment", "latest payment")):
            return self._answer_payments(profile) or CONTACT_FALLBACK

        if any(
            token in q
            for token in (
                "invoice",
                "balance",
                "outstanding",
                "overdue",
                "due",
                "owe",
                "unpaid",
            )
        ):
            return self._answer_invoices(profile) or CONTACT_FALLBACK

        if " paid" in f" {q}" or q.startswith("paid") or "was my payment" in q:
            return self._answer_payments(profile) or CONTACT_FALLBACK

        if any(
            token in q
            for token in (
                "contract",
                "lease",
                "room",
                "residence",
                "building",
                "rent amount",
                "how much is my rent",
                "my rent",
                "start",
                "end",
                "active",
                "staying",
                "renting",
            )
        ):
            return self._answer_contracts(question, profile) or CONTACT_FALLBACK

        summary = self._summary(profile)
        return summary or CONTACT_FALLBACK

    def _answer_profile(self, profile: RentProfile) -> str | None:
        data = profile.profile if isinstance(profile.profile, dict) else None
        if data is None and profile.profile is not None:
            data = profile.profile.model_dump(exclude_none=True)  # type: ignore[union-attr]
        if not data:
            return None
        lines = ["Here are your account details:"]
        if data.get("name"):
            lines.append(f"• Name: {data['name']}")
        if data.get("email"):
            lines.append(f"• Email: {data['email']}")
        if data.get("phone"):
            lines.append(f"• Phone: {data['phone']}")
        if data.get("address"):
            lines.append(f"• Address: {data['address']}")
        return "\n".join(lines) if len(lines) > 1 else None

    def _answer_contracts(self, question: str, profile: RentProfile) -> str | None:
        if not profile.contracts:
            return None

        q = (question or "").lower()
        active = [
            c for c in profile.contracts
            if (c.status or "").lower() in _ACTIVE_STATUSES
        ]
        focus = active or profile.contracts
        primary = focus[0]

        room = primary.room_number or (
            primary.room.get("room_number") if isinstance(primary.room, dict) else None
        )
        bldg = primary.building_name or (
            primary.building.get("building_name") if isinstance(primary.building, dict) else None
        )
        rent = primary.monthly_rent_amount
        number = primary.contract_number or primary.id

        if "end" in q and "start" not in q:
            if not primary.end_date:
                return None
            return f"Your active rent contract ends on {primary.end_date}."

        if "start" in q:
            if not primary.start_date:
                return None
            return f"Your active rent contract starts on {primary.start_date}."

        if "status" in q:
            if not primary.status:
                return None
            return f"Your contract status is {primary.status}."

        if "room" in q or "renting" in q:
            if not room:
                return None
            detail = f"You are renting room {room}"
            if bldg:
                detail += f" at {bldg}"
            return detail + "."

        if "residence" in q or "building" in q or "staying" in q:
            if not bldg:
                return None
            detail = f"You are staying at {bldg}"
            if room:
                detail += f", room {room}"
            return detail + "."

        if "how much" in q or "rent amount" in q or "my rent" in q:
            if rent is None:
                return None
            return f"Your rent is {rent:,.2f} per month."

        lines = ["Your active contract details:"] if active else ["Your contract details:"]
        for c in focus[:5]:
            c_room = c.room_number or (
                c.room.get("room_number") if isinstance(c.room, dict) else None
            )
            c_bldg = c.building_name or (
                c.building.get("building_name") if isinstance(c.building, dict) else None
            )
            c_rent = (
                f"{c.monthly_rent_amount:,.2f}/month"
                if c.monthly_rent_amount is not None
                else None
            )
            parts = [f"Contract #{c.contract_number or c.id}"]
            if c.status:
                parts.append(f"status {c.status}")
            if c_room:
                parts.append(f"room {c_room}")
            if c_bldg:
                parts.append(f"residence {c_bldg}")
            if c_rent:
                parts.append(f"rent {c_rent}")
            if c.start_date:
                parts.append(f"start {c.start_date}")
            if c.end_date:
                parts.append(f"end {c.end_date}")
            lines.append("• " + " · ".join(parts))

        if number and primary.status:
            return "\n".join(lines)
        return "\n".join(lines) if len(lines) > 1 else None

    def _answer_invoices(self, profile: RentProfile) -> str | None:
        if not profile.invoices and not profile.dashboard:
            return None
        unpaid = [
            inv for inv in profile.invoices
            if (inv.status or "").lower() in _UNPAID_STATUSES
        ]
        overdue = [
            inv for inv in unpaid
            if (inv.status or "").lower() == "overdue"
        ]
        outstanding = sum(_invoice_balance(inv) for inv in unpaid)
        lines = ["Your invoice summary:"]
        if unpaid:
            lines.append(f"• Outstanding balance: {outstanding:,.2f}")
            lines.append(f"• Unpaid invoices: {len(unpaid)}")
            if overdue:
                lines.append(f"• Overdue invoices: {len(overdue)}")
            next_due = sorted(
                (inv for inv in unpaid if inv.due_date),
                key=lambda inv: inv.due_date or "",
            )
            if next_due:
                inv = next_due[0]
                lines.append(
                    f"• Next due: invoice #{inv.invoice_number or inv.id}"
                    f" · {_invoice_balance(inv):,.2f}"
                    f" · due {inv.due_date}"
                )
            for inv in unpaid[:5]:
                lines.append(
                    f"• Invoice #{inv.invoice_number or inv.id}"
                    f" · {_invoice_balance(inv):,.2f}"
                    f" · {inv.status}"
                    + (f" · due {inv.due_date}" if inv.due_date else "")
                )
        else:
            lines.append("• No unpaid invoices on your account.")
            if profile.dashboard and profile.dashboard.get("paid_invoices"):
                lines.append(
                    f"• Paid invoices: {profile.dashboard.get('paid_invoices')}"
                )
            if profile.invoices:
                latest = profile.invoices[0]
                lines.append(
                    f"• Latest invoice: #{latest.invoice_number or latest.id}"
                    + (f" · {latest.total_amount:,.2f}" if latest.total_amount is not None else "")
                    + (f" · {latest.status}" if latest.status else "")
                )
        return "\n".join(lines)

    def _answer_payments(self, profile: RentProfile) -> str | None:
        if not profile.payments:
            return None
        lines = ["Your payment history:"]
        latest = profile.payments[0]
        lines.append(
            "• Latest payment:"
            + (f" {latest.amount:,.2f}" if latest.amount is not None else "")
            + (f" on {latest.payment_date}" if latest.payment_date else "")
            + (f" · status {latest.status}" if latest.status else "")
            + (f" · invoice #{latest.invoice_number}" if latest.invoice_number else "")
        )
        for status in ("approved", "pending", "rejected"):
            count = sum(1 for p in profile.payments if (p.status or "").lower() == status)
            if count:
                lines.append(f"• {status.capitalize()} payments: {count}")
        for payment in profile.payments[:5]:
            lines.append(
                "•"
                + (f" {payment.amount:,.2f}" if payment.amount is not None else " Payment")
                + (f" on {payment.payment_date}" if payment.payment_date else "")
                + (f" · {payment.status}" if payment.status else "")
                + (f" · invoice #{payment.invoice_number}" if payment.invoice_number else "")
            )
        return "\n".join(lines)

    def _answer_receipts(self, profile: RentProfile) -> str | None:
        if not profile.receipts:
            linked = [p for p in profile.payments if p.receipt_id or p.receipt_number]
            if not linked:
                return None
            lines = ["Receipts linked to your payments:"]
            for payment in linked[:5]:
                lines.append(
                    "•"
                    + (f" Receipt #{payment.receipt_number}" if payment.receipt_number else " Receipt available")
                    + (f" · payment on {payment.payment_date}" if payment.payment_date else "")
                    + (f" · status {payment.receipt_status}" if payment.receipt_status else "")
                )
            return "\n".join(lines)

        lines = [f"You have {len(profile.receipts)} receipt(s) available:"]
        for receipt in profile.receipts[:5]:
            lines.append(
                f"• Receipt #{receipt.receipt_number or receipt.id}"
                + (f" · {receipt.display_status or receipt.status}" if (receipt.display_status or receipt.status) else "")
                + (f" · issued {receipt.issued_at}" if receipt.issued_at else "")
                + (f" · invoice #{receipt.invoice_number}" if receipt.invoice_number else "")
            )
        return "\n".join(lines)

    def _answer_utilities(self, profile: RentProfile) -> str | None:
        utilities = _utility_invoices(profile.invoices)
        if not utilities:
            return None
        latest = utilities[0]
        lines = ["Your utility bills:"]
        lines.append(
            f"• Latest: invoice #{latest.invoice_number or latest.id}"
            + (f" · {latest.total_amount:,.2f}" if latest.total_amount is not None else "")
            + (f" · {latest.status}" if latest.status else "")
            + (f" · period {latest.billing_period or latest.billing_month}" if (latest.billing_period or latest.billing_month) else "")
        )
        for inv in utilities[:5]:
            lines.append(
                f"• Invoice #{inv.invoice_number or inv.id}"
                + (f" · {inv.total_amount:,.2f}" if inv.total_amount is not None else "")
                + (f" · {inv.status}" if inv.status else "")
            )
        return "\n".join(lines)

    def _answer_maintenance(self, profile: RentProfile) -> str | None:
        if not profile.maintenance_requests:
            return None
        lines = [f"You have {len(profile.maintenance_requests)} maintenance request(s):"]
        for req in profile.maintenance_requests[:5]:
            lines.append(
                f"• #{req.id}"
                + (f" · {req.title}" if req.title else "")
                + (f" · status {req.status}" if req.status else "")
                + (f" · room {req.room_number}" if req.room_number else "")
            )
        return "\n".join(lines)

    def _answer_notifications(self, profile: RentProfile) -> str | None:
        if not profile.notifications:
            return None
        lines = [f"You have {len(profile.notifications)} notification(s):"]
        for note in profile.notifications[:8]:
            lines.append(
                "•"
                + (f" {note.title}" if note.title else " Notification")
                + (f" · {note.status}" if note.status else "")
            )
        return "\n".join(lines)

    def _answer_documents(self, profile: RentProfile) -> str | None:
        docs = profile.documents or {}
        if not docs:
            return None
        lines = ["Documents available in your portal:"]
        mapping = [
            ("contract_documents", "Contracts"),
            ("invoice_documents", "Invoices"),
            ("receipt_documents", "Receipts"),
            ("utility_bill_documents", "Utility bills"),
        ]
        any_docs = False
        for key, label in mapping:
            items = docs.get(key) or []
            if items:
                any_docs = True
                lines.append(f"• {label}: {len(items)} available")
        return "\n".join(lines) if any_docs else None

    def _summary(self, profile: RentProfile) -> str | None:
        parts: list[str] = []
        contract = self._answer_contracts("active contract", profile)
        invoices = self._answer_invoices(profile)
        if contract:
            parts.append(contract)
        if invoices:
            parts.append(invoices)
        if profile.payments:
            parts.append(self._answer_payments(profile) or "")
        return "\n\n".join(p for p in parts if p) or None


def _utility_invoices(invoices: list[Invoice]) -> list[Invoice]:
    return [
        inv
        for inv in invoices
        if (inv.invoice_type or inv.type or "").lower() == "utility"
    ]


def _invoice_balance(inv: Invoice) -> float:
    for value in (inv.remaining_balance, inv.balance_due, inv.total_amount, inv.amount):
        if value is not None:
            return float(value)
    return 0.0
