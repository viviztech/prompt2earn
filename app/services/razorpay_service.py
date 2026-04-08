import hmac
import hashlib
import razorpay
import logging
from decimal import Decimal
from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


def get_razorpay_client():
    return razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))


def create_order(amount_inr: Decimal, user_id: str, plan_id: str) -> dict:
    client = get_razorpay_client()
    amount_paise = int(amount_inr * 100)
    receipt = f"sub_{user_id[:8]}_{plan_id[:8]}"
    order = client.order.create({
        "amount": amount_paise,
        "currency": "INR",
        "receipt": receipt,
        "notes": {"user_id": str(user_id), "plan_id": str(plan_id)},
    })
    return {
        "order_id": order["id"],
        "key": settings.RAZORPAY_KEY_ID,
        "amount": amount_paise,
        "currency": "INR",
    }


def verify_payment_signature(order_id: str, payment_id: str, signature: str) -> bool:
    message = f"{order_id}|{payment_id}"
    expected = hmac.new(
        settings.RAZORPAY_KEY_SECRET.encode(),
        message.encode(),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


def verify_webhook_signature(payload_body: bytes, signature: str) -> bool:
    expected = hmac.new(
        settings.RAZORPAY_WEBHOOK_SECRET.encode(),
        payload_body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)
