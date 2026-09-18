"""Domain entities.

These mirror the shape served by the Laravel backend (em_backend).
Every model is lenient (extra="allow", all fields optional) — the LLM grounding
layer reads whatever is present and never assumes a rigid schema.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, field_validator


class _Lenient(BaseModel):
    model_config = ConfigDict(extra="allow")


class Property(_Lenient):
    id: int | None = None
    property_name: str | None = None
    property_code: str | None = None
    property_type: str | None = None
    building_name: str | None = None
    building_location: str | None = None
    township: str | None = None
    address: str | None = None
    room_number: str | None = None
    floor_number: int | None = None
    type: str | None = None  # rent | sale | both
    purpose: str | None = None
    status: str | None = None
    monthly_rent: float | None = None
    rent_price: float | None = None
    sale_price: float | None = None
    deposit: float | None = None
    rent_deposit_price: float | None = None
    booking_deposit_price: float | None = None
    area_sqft: float | None = None
    width_ft: float | None = None
    length_ft: float | None = None
    bedrooms: int | None = None
    bathrooms: int | None = None
    amenities: list[str] = []
    description: str | None = None
    featured_image: str | None = None
    gallery_images: list[str] = []
    city: str | None = None

    @field_validator("amenities", "gallery_images", mode="before")
    @classmethod
    def _default_list(cls, value: object) -> object:
        return [] if value is None else value

    @field_validator(
        "monthly_rent",
        "rent_price",
        "sale_price",
        "deposit",
        "rent_deposit_price",
        "booking_deposit_price",
        "area_sqft",
        "width_ft",
        "length_ft",
        mode="before",
    )
    @classmethod
    def _empty_number_to_none(cls, value: object) -> object:
        if value == "" or value is None:
            return None
        return value


class Contract(_Lenient):
    id: int | None = None
    contract_number: str | None = None
    type: str | None = None  # rent | sale
    status: str | None = None  # active | completed | pending | terminated
    start_date: str | None = None
    end_date: str | None = None
    monthly_rent_amount: float | None = None
    deposit_amount: float | None = None
    sale_price: float | None = None
    room_number: str | None = None
    building_name: str | None = None
    room: dict | None = None
    building: dict | None = None


class Invoice(_Lenient):
    id: int | None = None
    invoice_number: str | None = None
    status: str | None = None  # paid | unpaid | partial | overdue | issued
    total_amount: float | None = None
    paid_amount: float | None = None
    balance_due: float | None = None
    amount: float | None = None
    billing_month: str | None = None
    due_date: str | None = None
    issued_at: str | None = None


class Payment(_Lenient):
    id: int | None = None
    payment_number: str | None = None
    amount: float | None = None
    payment_date: str | None = None
    payment_method: str | dict | None = None
    status: str | None = None  # approved | pending | rejected
    invoice_id: int | None = None


class RentProfile(_Lenient):
    """Aggregate of everything that grounds a 'my rent' answer for one user."""

    dashboard: dict | None = None
    contracts: list[Contract] = []
    invoices: list[Invoice] = []
    payments: list[Payment] = []
