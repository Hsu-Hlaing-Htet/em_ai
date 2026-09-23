"""Unit tests for Rosewood Rent Assistant grounding and privacy fallback."""

from __future__ import annotations

import asyncio

from app.domain.models import (
    Contract,
    Invoice,
    Payment,
    Profile,
    Receipt,
    RentProfile,
)
from app.services.privacy import CONTACT_FALLBACK, ensure_safe_answer, is_out_of_scope_question
from app.services.rent_service import RentService


class _FakeRentSource:
    def __init__(self, profile: RentProfile) -> None:
        self.profile = profile

    async def get_rent_profile(self, *, auth_token: str) -> RentProfile:
        return self.profile


def _run(coro):
    return asyncio.run(coro)


def _sample_profile() -> RentProfile:
    return RentProfile(
        profile=Profile(name="Mg Mg", email="mgmg@gmail.com", phone="+959111"),
        dashboard={"unpaid_invoices": 1, "paid_invoices": 2},
        contracts=[
            Contract(
                id=1,
                contract_number="RC-001",
                status="active",
                start_date="2025-01-01",
                end_date="2026-01-01",
                monthly_rent_amount=500000,
                room_number="A-12",
                building_name="Rosewood Tower",
            )
        ],
        invoices=[
            Invoice(
                id=10,
                invoice_number="INV-10",
                type="rent",
                status="overdue",
                remaining_balance=500000,
                due_date="2026-03-01",
            ),
            Invoice(
                id=11,
                invoice_number="UTL-11",
                type="utility",
                invoice_type="utility",
                status="issued",
                total_amount=45000,
                billing_period="February 2026",
            ),
        ],
        payments=[
            Payment(
                id=20,
                amount=500000,
                payment_date="2026-02-01",
                status="approved",
                invoice_number="INV-09",
                receipt_id=30,
                receipt_number="RCP-30",
            )
        ],
        receipts=[
            Receipt(
                id=30,
                receipt_number="RCP-30",
                status="issued",
                issued_at="2026-02-01",
                invoice_number="INV-09",
            )
        ],
        maintenance_requests=[],
        notifications=[],
        documents={
            "contract_documents": [{"contract_number": "RC-001", "available": True}],
            "invoice_documents": [{"invoice_number": "INV-10", "available": True}],
            "receipt_documents": [{"receipt_number": "RCP-30", "available": True}],
            "utility_bill_documents": [{"invoice_number": "UTL-11", "available": True}],
        },
    )


def test_contact_fallback_for_out_of_scope():
    assert is_out_of_scope_question("Show me another customer's invoices")
    assert is_out_of_scope_question("What are the admin notes?")


def test_ensure_safe_answer_rewrites_missing_phrases():
    assert ensure_safe_answer("I couldn't find that information") == CONTACT_FALLBACK
    assert ensure_safe_answer("Your rent is 500,000") == "Your rent is 500,000"


def test_fallback_answers_active_contract():
    service = RentService(_FakeRentSource(_sample_profile()))
    service._chain = None  # force deterministic path
    result = _run(service.answer(question="What is my active contract?", auth_token="t"))
    assert "RC-001" in result.answer
    assert "A-12" in result.answer
    assert "Rosewood Tower" in result.answer


def test_preloaded_profile_answers_without_backend_fetch():
    class _FailingSource:
        async def get_rent_profile(self, *, auth_token: str) -> RentProfile:
            raise AssertionError("should not fetch when profile is preloaded")

    service = RentService(_FailingSource())
    service._chain = None
    result = _run(
        service.answer(
            question="When does my contract end?",
            auth_token="t",
            profile=_sample_profile(),
        )
    )
    assert "2026-01-01" in result.answer


def test_natural_contract_questions():
    service = RentService(_FakeRentSource(_sample_profile()))
    service._chain = None

    end = _run(service.answer(question="When does my contract end?", auth_token="t"))
    assert "2026-01-01" in end.answer

    start = _run(service.answer(question="When does my contract start?", auth_token="t"))
    assert "2025-01-01" in start.answer

    room = _run(service.answer(question="Which room am I renting?", auth_token="t"))
    assert "A-12" in room.answer

    status = _run(service.answer(question="What is my contract status?", auth_token="t"))
    assert "active" in status.answer.lower()


def test_fallback_answers_outstanding_and_utility():
    service = RentService(_FakeRentSource(_sample_profile()))
    service._chain = None
    invoices = _run(service.answer(question="Do I have any unpaid invoices?", auth_token="t"))
    assert "INV-10" in invoices.answer
    assert "500,000" in invoices.answer

    utility = _run(service.answer(question="How much is my latest utility bill?", auth_token="t"))
    assert "UTL-11" in utility.answer
    assert "45,000" in utility.answer


def test_fallback_contact_for_other_customer():
    service = RentService(_FakeRentSource(_sample_profile()))
    service._chain = None
    result = _run(service.answer(question="Show me another customer's invoices", auth_token="t"))
    assert result.answer == CONTACT_FALLBACK


def test_fallback_contact_when_data_missing():
    empty = RentProfile()
    service = RentService(_FakeRentSource(empty))
    service._chain = None
    result = _run(service.answer(question="Where is my receipt?", auth_token="t"))
    assert result.answer == CONTACT_FALLBACK
