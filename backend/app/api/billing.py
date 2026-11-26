"""Subscription, 7-day free trial, checkout, and payment webhook API routes."""

import json
from datetime import UTC, datetime
from typing import Annotated, Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.core.billing import (
    AccessEntitlements,
    PaymentProvider,
    PlanDefinition,
    PlanId,
    compute_entitlements,
    get_plan,
    list_plans,
)
from app.db import (
    PaymentRepository,
    PaymentTransactionRecord,
    ProfileRepository,
    SubscriptionRecord,
    SubscriptionRepository,
    get_db,
)
from app.services import PaymentGatewayService, verify_payment_webhook_signature

router = APIRouter(tags=["billing", "subscriptions"])


def get_billing_settings() -> Settings:
    """FastAPI dependency returning runtime billing and gateway settings."""
    return get_settings()


def get_payment_gateway(
    settings: Annotated[Settings, Depends(get_billing_settings)],
) -> PaymentGatewayService:
    """FastAPI dependency returning the configured PaymentGatewayService."""
    return PaymentGatewayService(settings=settings)


DbSession = Annotated[Session, Depends(get_db)]
BillingSettingsDep = Annotated[Settings, Depends(get_billing_settings)]
PaymentGatewayDep = Annotated[PaymentGatewayService, Depends(get_payment_gateway)]


class BillingStatusResponse(BaseModel):
    """Combined subscription state, entitlements, trial eligibility, and transaction history."""

    user_id: str
    subscription: SubscriptionRecord | None = None
    entitlements: AccessEntitlements
    trial_eligible: bool
    transactions: list[PaymentTransactionRecord] = Field(default_factory=list)


class CheckoutRequest(BaseModel):
    """Payload to start a subscription checkout with a Pakistani or Overseas gateway."""

    plan_id: PlanId
    provider: PaymentProvider


class CheckoutResponse(BaseModel):
    """Created pending transaction plus hosted or sandbox checkout URL."""

    transaction: PaymentTransactionRecord
    checkout_url: str
    sandbox_mode: bool
    instructions: str


class PaymentWebhookPayload(BaseModel):
    """Normalized gateway webhook payload handled by POST /webhooks/payments/{provider}."""

    order_id: str = Field(..., min_length=1)
    event: Literal["payment.succeeded", "payment.failed", "payment.refunded"]
    provider_reference: str | None = None


class PaymentWebhookAckResponse(BaseModel):
    """Acknowledgement returned to payment gateway webhooks."""

    status: str = "ok"
    already_processed: bool = False
    transaction: PaymentTransactionRecord
    subscription: SubscriptionRecord | None = None


@router.get("/api/v1/billing/plans", response_model=list[PlanDefinition])
def get_billing_plans() -> list[PlanDefinition]:
    """List all FitSoul AI trial, Pakistani PKR, and Overseas USD subscription plans."""
    return list_plans()


@router.get("/api/v1/billing/{user_id}/subscription", response_model=BillingStatusResponse)
def read_billing_status(user_id: str, db: DbSession) -> BillingStatusResponse:
    """Return a user's subscription state, effective feature entitlements, and transactions."""
    profile = ProfileRepository.get_profile(db, user_id)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")

    sub = SubscriptionRepository.get_subscription(db, user_id)
    if sub is None:
        _resolved_status, entitlements = compute_entitlements(None, None, None)
        trial_eligible = True
    else:
        resolved_status, entitlements = compute_entitlements(sub.plan, sub.status, sub.expires_at)
        sub = sub.model_copy(update={"status": resolved_status.value})
        trial_eligible = False

    transactions = PaymentRepository.list_user_transactions(db, user_id, limit=20)
    return BillingStatusResponse(
        user_id=user_id,
        subscription=sub,
        entitlements=entitlements,
        trial_eligible=trial_eligible,
        transactions=transactions,
    )


@router.post(
    "/api/v1/billing/{user_id}/trial",
    response_model=SubscriptionRecord,
    status_code=status.HTTP_201_CREATED,
)
def start_free_trial(user_id: str, db: DbSession) -> SubscriptionRecord:
    """Activate a one-time 7-day free trial if the user has no prior subscription."""
    profile = ProfileRepository.get_profile(db, user_id)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")

    sub, created = SubscriptionRepository.start_trial_if_none(db, user_id)
    if not created:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Free trial already used or subscription already exists",
        )
    return sub


@router.post(
    "/api/v1/billing/{user_id}/checkout",
    response_model=CheckoutResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_checkout(
    user_id: str,
    payload: CheckoutRequest,
    db: DbSession,
    settings: BillingSettingsDep,
    gateway: PaymentGatewayDep,
) -> CheckoutResponse:
    """Initiate a checkout session for a paid plan and persist a pending transaction."""
    profile = ProfileRepository.get_profile(db, user_id)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")

    if payload.plan_id == PlanId.TRIAL:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Use /trial endpoint to activate the free trial",
        )

    try:
        plan_def = get_plan(payload.plan_id)
        order_id = f"fs_{uuid4().hex[:16]}"
        session_info = gateway.create_checkout_session(
            user_id,
            plan_def,
            payload.provider,
            order_id,
            pwa_base_url=settings.pwa_base_url,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    transaction = PaymentRepository.create_transaction(
        db,
        user_id=user_id,
        plan=plan_def.id.value,
        provider=payload.provider.value,
        amount=plan_def.price_amount,
        currency=plan_def.currency,
        provider_order_id=order_id,
        checkout_url=session_info.checkout_url,
        metadata_json={"sandbox_mode": session_info.sandbox_mode},
    )
    return CheckoutResponse(
        transaction=transaction,
        checkout_url=session_info.checkout_url,
        sandbox_mode=session_info.sandbox_mode,
        instructions=session_info.instructions,
    )


@router.post("/api/v1/billing/{user_id}/cancel", response_model=SubscriptionRecord)
def cancel_user_subscription(user_id: str, db: DbSession) -> SubscriptionRecord:
    """Cancel an existing subscription (moves user back to limited mode)."""
    profile = ProfileRepository.get_profile(db, user_id)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")

    cancelled = SubscriptionRepository.cancel_subscription(db, user_id)
    if cancelled is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active subscription found",
        )
    return cancelled


@router.post("/webhooks/payments/{provider}", response_model=PaymentWebhookAckResponse)
async def handle_payment_webhook(
    provider: str,
    request: Request,
    db: DbSession,
    settings: BillingSettingsDep,
) -> PaymentWebhookAckResponse:
    """Verify gateway webhook, update transaction idempotently, and activate or cancel plan."""
    try:
        parsed_provider = PaymentProvider(provider.strip().lower())
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported payment provider '{provider}'",
        ) from exc

    raw_body = await request.body()
    secret = settings.payment_webhook_secret.strip()
    if secret:
        sig = request.headers.get("X-Payment-Signature")
        if not verify_payment_webhook_signature(raw_body, sig, secret):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid payment webhook signature",
            )

    try:
        raw_payload = json.loads(raw_body.decode("utf-8"))
        webhook_data = PaymentWebhookPayload.model_validate(raw_payload)
    except (UnicodeDecodeError, json.JSONDecodeError, ValidationError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid webhook payload",
        ) from exc

    tx = PaymentRepository.get_by_order_id(db, webhook_data.order_id)
    if tx is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment order not found",
        )
    if tx.provider != parsed_provider.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Webhook provider does not match payment order provider",
        )

    if tx.status == "paid" and webhook_data.event == "payment.succeeded":
        existing_sub = SubscriptionRepository.get_subscription(db, tx.user_id)
        return PaymentWebhookAckResponse(
            status="ok",
            already_processed=True,
            transaction=tx,
            subscription=existing_sub,
        )

    metadata_update = (
        {"provider_reference": webhook_data.provider_reference}
        if webhook_data.provider_reference
        else None
    )

    if webhook_data.event == "payment.succeeded":
        now = datetime.now(UTC)
        updated_tx = PaymentRepository.mark_transaction_status(
            db,
            tx.provider_order_id,
            "paid",
            metadata_update=metadata_update,
            paid_at=now,
        )
        sub = SubscriptionRepository.activate_paid_plan(
            db,
            tx.user_id,
            PlanId(tx.plan),
            parsed_provider,
            now=now,
        )
        assert updated_tx is not None
        return PaymentWebhookAckResponse(
            status="ok",
            already_processed=False,
            transaction=updated_tx,
            subscription=sub,
        )

    if webhook_data.event == "payment.failed":
        updated_tx = PaymentRepository.mark_transaction_status(
            db,
            tx.provider_order_id,
            "failed",
            metadata_update=metadata_update,
        )
        assert updated_tx is not None
        return PaymentWebhookAckResponse(
            status="ok",
            already_processed=False,
            transaction=updated_tx,
            subscription=SubscriptionRepository.get_subscription(db, tx.user_id),
        )

    updated_tx = PaymentRepository.mark_transaction_status(
        db,
        tx.provider_order_id,
        "refunded",
        metadata_update=metadata_update,
    )
    cancelled_sub = SubscriptionRepository.cancel_subscription(db, tx.user_id)
    assert updated_tx is not None
    return PaymentWebhookAckResponse(
        status="ok",
        already_processed=False,
        transaction=updated_tx,
        subscription=cancelled_sub,
    )
