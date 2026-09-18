"""Use case: answer a question about the user's own rent, grounded in backend data."""

from __future__ import annotations

from dataclasses import dataclass

from app.core.logging import get_logger
from app.domain.models import RentProfile
from app.domain.ports import RentDataSource
from app.llm.chains import build_rent_chain
from app.services.context import to_context

logger = get_logger(__name__)


@dataclass
class RentAnswer:
    answer: str
    profile: RentProfile


class RentService:
    def __init__(self, data_source: RentDataSource) -> None:
        self._data_source = data_source
        self._chain = build_rent_chain()

    async def answer(self, *, question: str, auth_token: str) -> RentAnswer:
        profile = await self._data_source.get_rent_profile(auth_token=auth_token)

        context = "\n\n".join(
            [
                to_context("DASHBOARD", profile.dashboard or {}),
                to_context("CONTRACTS", profile.contracts),
                to_context("INVOICES", profile.invoices),
                to_context("PAYMENTS", profile.payments),
            ]
        )

        if self._chain is not None:
            try:
                answer = await self._chain.ainvoke({"context": context, "question": question})
            except Exception as exc:
                logger.warning("LLM chain failed: %s; falling back to grounded formatter", exc)
                answer = self._fallback_answer(question, profile)
        else:
            answer = self._fallback_answer(question, profile)

        return RentAnswer(answer=answer, profile=profile)

    def _fallback_answer(self, question: str, profile: RentProfile) -> str:
        unpaid_invoices = [
            inv for inv in profile.invoices
            if (inv.status or '').lower() in {'issued', 'unpaid', 'partial', 'overdue'}
        ]
        active_contracts = [
            c for c in profile.contracts
            if (c.status or '').lower() in {'active', 'approved'}
        ]

        lines = ["Here is a summary of your rent and account status:\n"]

        # Contracts
        if active_contracts:
            lines.append("**Active Leases / Contracts:**")
            for c in active_contracts:
                rent = f"${c.monthly_rent_amount:,.2f}/month" if c.monthly_rent_amount else "N/A"
                room = c.room_number or (c.room.get('room_number') if isinstance(c.room, dict) else 'Unit')
                bldg = c.building_name or (c.building.get('building_name') if isinstance(c.building, dict) else 'Rosewood')
                period = f" ({c.start_date or ''} to {c.end_date or 'Ongoing'})" if (c.start_date or c.end_date) else ""
                lines.append(f"• Contract #{c.contract_number or c.id}: {bldg} Unit {room} — {rent}{period}")
        else:
            lines.append("• No active contracts found on your account.")

        # Invoices / Balances
        lines.append("\n**Billing & Invoices:**")
        if unpaid_invoices:
            lines.append(f"• You have **{len(unpaid_invoices)} unpaid or pending invoice(s)**:")
            for inv in unpaid_invoices[:5]:
                due = f"due on {inv.due_date}" if inv.due_date else ""
                balance = inv.balance_due or inv.total_amount or inv.amount or 0
                lines.append(f"  - Invoice #{inv.invoice_number or inv.id}: ${balance:,.2f} {due} [{inv.status.upper()}]")
        else:
            lines.append("• All your invoices are currently paid in full. You have no overdue balance!")

        # Recent Payments
        if profile.payments:
            latest = profile.payments[0]
            amt = f"${latest.amount:,.2f}" if latest.amount else ""
            dt = f" on {latest.payment_date}" if latest.payment_date else ""
            lines.append(f"\n**Latest Payment:** {amt}{dt} (Status: {latest.status or 'Processed'})")

        return "\n".join(lines)
