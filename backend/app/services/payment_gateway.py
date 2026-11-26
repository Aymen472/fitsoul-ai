"""Payment gateway checkout builder and HMAC webhook signature verifier."""

import hashlib
import hmac
from urllib.parse import urlencode

from pydantic import BaseModel

from app.config import Settings, get_settings
from app.core.billing import PaymentProvider, PlanDefinition


class CheckoutSessionResult(BaseModel):
    """Hosted or sandbox payment checkout link plus user instructions."""

    provider: PaymentProvider
    order_id: str
    checkout_url: str
    sandbox_mode: bool
    instructions: str


def verify_payment_webhook_signature(
    raw_body: bytes,
    signature_header: str | None,
    secret: str,
) -> bool:
    """Verify HMAC-SHA256 signature accepting either bare hex digest or 'sha256=<hex>'."""
    clean_secret = secret.strip()
    if not clean_secret or not signature_header:
        return False

    header = signature_header.strip()
    digest = header[7:] if header.lower().startswith("sha256=") else header
    if not digest:
        return False

    expected = hmac.new(clean_secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, digest)


_PROVIDER_INSTRUCTIONS: dict[PaymentProvider, str] = {
    PaymentProvider.SAFEPAY: (
        "Complete card or bank transfer checkout securely via Safepay Pakistan."
    ),
    PaymentProvider.PAYFAST: (
        "Pay with Pakistani Visa/Mastercard, UnionPay, or mobile wallet via PayFast."
    ),
    PaymentProvider.JAZZCASH: (
        "Approve the JazzCash mobile wallet prompt on your phone using your MPIN."
    ),
    PaymentProvider.EASYPAISA: (
        "Confirm the Easypaisa payment request in your Easypaisa app or USSD OTP."
    ),
    PaymentProvider.LEMONSQUEEZY: (
        "Complete international Visa, Mastercard, or Apple Pay checkout via LemonSqueezy."
    ),
    PaymentProvider.MOCK: (
        "Local sandbox checkout ready — click 'Complete Sandbox Payment' to simulate webhook."
    ),
}


class PaymentGatewayService:
    """Gateway abstraction for Safepay, PayFast, JazzCash, Easypaisa, LemonSqueezy, and Mock."""

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        safepay_api_key: str | None = None,
        safepay_env: str | None = None,
        payfast_merchant_id: str | None = None,
        payfast_secured_key: str | None = None,
        lemonsqueezy_api_key: str | None = None,
    ) -> None:
        cfg = settings or get_settings()
        self.safepay_api_key = (
            cfg.safepay_api_key if safepay_api_key is None else safepay_api_key
        ).strip()
        self.safepay_env = (cfg.safepay_env if safepay_env is None else safepay_env).strip()
        self.payfast_merchant_id = (
            cfg.payfast_merchant_id if payfast_merchant_id is None else payfast_merchant_id
        ).strip()
        self.payfast_secured_key = (
            cfg.payfast_secured_key if payfast_secured_key is None else payfast_secured_key
        ).strip()
        self.lemonsqueezy_api_key = (
            cfg.lemonsqueezy_api_key if lemonsqueezy_api_key is None else lemonsqueezy_api_key
        ).strip()

    def is_live_configured(self, provider: PaymentProvider) -> bool:
        """Return True when production credentials for `provider` are configured."""
        if provider == PaymentProvider.SAFEPAY:
            return bool(self.safepay_api_key and self.safepay_env.lower() == "production")
        if provider in {
            PaymentProvider.PAYFAST,
            PaymentProvider.JAZZCASH,
            PaymentProvider.EASYPAISA,
        }:
            return bool(self.payfast_merchant_id and self.payfast_secured_key)
        if provider == PaymentProvider.LEMONSQUEEZY:
            return bool(self.lemonsqueezy_api_key)
        return False

    def create_checkout_session(
        self,
        user_id: str,
        plan_def: PlanDefinition,
        provider: PaymentProvider,
        order_id: str,
        *,
        pwa_base_url: str,
    ) -> CheckoutSessionResult:
        """Validate provider support and generate a hosted or local sandbox checkout URL."""
        if provider not in plan_def.supported_providers:
            raise ValueError(
                f"Provider '{provider.value}' is not supported for plan '{plan_def.id.value}'"
            )

        sandbox_mode = not self.is_live_configured(provider)
        clean_base = pwa_base_url.strip().rstrip("/") or "http://localhost:3000"

        if sandbox_mode:
            query = urlencode(
                {
                    "checkout_order": order_id,
                    "provider": provider.value,
                    "plan": plan_def.id.value,
                }
            )
            checkout_url = f"{clean_base}/billing?{query}"
        elif provider == PaymentProvider.SAFEPAY:
            query = urlencode({"beacon": order_id, "ref": user_id})
            checkout_url = f"https://getsafepay.com/checkout?{query}"
        elif provider == PaymentProvider.LEMONSQUEEZY:
            query = urlencode({"order": order_id, "checkout[custom][user_id]": user_id})
            checkout_url = f"https://app.lemonsqueezy.com/checkout?{query}"
        else:
            query = urlencode({"BASKET_ID": order_id, "MERCHANT_ID": self.payfast_merchant_id})
            checkout_url = (
                f"https://ipg1.apps.net.pk/Ecommerce/api/Transaction/PostTransaction?{query}"
            )

        return CheckoutSessionResult(
            provider=provider,
            order_id=order_id,
            checkout_url=checkout_url,
            sandbox_mode=sandbox_mode,
            instructions=_PROVIDER_INSTRUCTIONS[provider],
        )
