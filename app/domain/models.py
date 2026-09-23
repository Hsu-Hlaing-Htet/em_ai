"""Domain entities.

These mirror the shape served by the Laravel backend (em_backend).
Every model is lenient (extra="allow", all fields optional) — the LLM grounding
layer reads whatever is present and never assumes a rigid schema.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, field_validator, model_validator


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
    room_price: float | str | None = None
    estimated_monthly_payment: float | str | None = None
    deposit_amount: float | None = None
    sale_price: float | None = None
    room_number: str | None = None
    building_name: str | None = None
    room: dict | None = None
    building: dict | None = None

    @model_validator(mode="after")
    def _coerce_monthly_rent(self) -> "Contract":
        if self.monthly_rent_amount is not None:
            return self

        candidates: list[object] = [
            self.estimated_monthly_payment,
            self.room_price,
        ]
        if isinstance(self.room, dict):
            candidates.append(self.room.get("rent_price"))

        for value in candidates:
            if value is None or value == "":
                continue
            try:
                self.monthly_rent_amount = float(value)
                break
            except (TypeError, ValueError):
                continue
        return self


class Invoice(_Lenient):
    id: int | None = None
    invoice_number: str | None = None
    type: str | None = None  # rent | utility | sale | maintenance | ...
    invoice_type: str | None = None
    status: str | None = None  # paid | unpaid | partial | overdue | issued
    payment_status: str | None = None
    total_amount: float | None = None
    paid_amount: float | None = None
    remaining_balance: float | None = None
    balance_due: float | None = None
    amount: float | None = None
    billing_month: str | None = None
    billing_period: str | None = None
    due_date: str | None = None
    issued_at: str | None = None
    issued_date: str | None = None
    room_number: str | None = None
    building_name: str | None = None
    property_unit: str | None = None


class Payment(_Lenient):
    id: int | None = None
    payment_number: str | None = None
    amount: float | None = None
    payment_date: str | None = None
    payment_method: str | dict | None = None
    payment_method_name: str | None = None
    status: str | None = None  # approved | pending | rejected
    invoice_id: int | None = None
    invoice_number: str | None = None
    invoice_type: str | None = None
    receipt_id: int | None = None
    receipt_number: str | None = None
    receipt_status: str | None = None


class Receipt(_Lenient):
    id: int | None = None
    receipt_number: str | None = None
    status: str | None = None
    display_status: str | None = None
    delivery_status: str | None = None
    is_sent: bool | None = None
    issued_at: str | None = None
    sent_at: str | None = None
    invoice_number: str | None = None
    amount: float | None = None
    paid_amount: float | None = None
    payment_date: str | None = None
    room_number: str | None = None
    building_name: str | None = None


class MaintenanceRequest(_Lenient):
    id: int | None = None
    title: str | None = None
    category: str | None = None
    priority: str | None = None
    description: str | None = None
    status: str | None = None
    room_number: str | None = None
    building_name: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    rejection_reason: str | None = None
    resolution_note: str | None = None


class Notification(_Lenient):
    id: str | int | None = None
    type: str | None = None
    title: str | None = None
    message: str | None = None
    status: str | None = None
    created_at: str | None = None
    resource_id: int | None = None


class Profile(_Lenient):
    id: int | None = None
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    nrc: str | None = None
    dob: str | None = None
    gender: str | None = None
    address: str | None = None


class RentProfile(_Lenient):
    """Aggregate of everything that grounds a customer portal answer for one user."""

    dashboard: dict | None = None
    profile: Profile | dict | None = None
    contracts: list[Contract] = []
    invoices: list[Invoice] = []
    payments: list[Payment] = []
    receipts: list[Receipt] = []
    maintenance_requests: list[MaintenanceRequest] = []
    notifications: list[Notification] = []
    documents: dict | None = None
