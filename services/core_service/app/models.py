"""Core Service request models."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    email: str = Field(min_length=3)
    password: str = Field(min_length=8)
    name: str = Field(min_length=1)


class LoginRequest(BaseModel):
    email: str = Field(min_length=3)
    password: str = Field(min_length=1)


class PasswordResetRequest(BaseModel):
    email: str = Field(min_length=3)


class PasswordResetConfirmRequest(BaseModel):
    token: str
    password: str = Field(min_length=8)


class AddCartItemRequest(BaseModel):
    productId: str
    quantity: int = Field(gt=0)
    size: str | None = None
    variantId: str | None = None
    variant: dict[str, Any] | None = None


class UpdateCartItemRequest(BaseModel):
    quantity: int = Field(ge=0)
    size: str | None = None
    variantId: str | None = None


class Address(BaseModel):
    name: str
    line1: str
    line2: str | None = ""
    city: str
    region: str
    postalCode: str
    country: str
    phone: str


class CheckoutQuoteRequest(BaseModel):
    shippingAddress: Address
    clientTotals: dict[str, Any] | None = None


class PlaceOrderRequest(BaseModel):
    shippingAddress: Address
    paymentMethod: str = "demo"
    clientTotals: dict[str, Any] | None = None


class ReturnEligibilityRequest(BaseModel):
    orderId: str
    orderItemId: str


class ReturnItemRequest(BaseModel):
    orderItemId: str
    quantity: int = Field(gt=0)
    reason: str
    condition: str
    resolution: str


class CreateReturnRequest(BaseModel):
    orderId: str
    items: list[ReturnItemRequest]


class CreateSupportTicketRequest(BaseModel):
    category: str
    priority: str
    subject: str
    body: str
    orderId: str | None = None


class AddTicketMessageRequest(BaseModel):
    message: str


class ActivityEventRequest(BaseModel):
    eventType: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class SavePreferenceRequest(BaseModel):
    key: str = Field(min_length=1)
    value: Any


class UpdatePhoneRequest(BaseModel):
    """Development-only phone-number verification request."""

    phoneNumber: str = Field(pattern=r"^\+[1-9]\d{1,14}$")


class VerifyCallerRequest(BaseModel):
    """Proof supplied by a voice caller before account data is disclosed."""

    orderNumber: str = Field(min_length=1)
    lastName: str | None = Field(default=None, min_length=1)
    postalCode: str | None = Field(default=None, min_length=1)
    callerPhoneNumber: str | None = Field(default=None, pattern=r"^\+[1-9]\d{1,14}$")


class OrderUpdateRequest(BaseModel):
    """The intentionally narrow set of order changes supported by voice."""

    action: Literal["cancel", "update_shipping_address"]
    shippingAddress: Address | None = None


class InternalActivityEventRequest(BaseModel):
    userId: str | None = None
    eventType: Literal["voice_call_started", "voice_call_verified", "voice_call_escalated", "voice_call_ended"]
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentToolAuditLogRequest(BaseModel):
    sessionId: str
    userId: str | None = None
    agentType: str
    toolName: str
    input: dict[str, Any] = Field(default_factory=dict)
    output: dict[str, Any] = Field(default_factory=dict)
    status: str
    requiresUserConfirmation: bool = False
    confirmedAt: str | None = None
