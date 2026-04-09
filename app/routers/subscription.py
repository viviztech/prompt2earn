import json
import logging
import uuid
from datetime import datetime, timedelta
from fastapi import APIRouter, Request, Depends, HTTPException, Form, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from app.database import get_db
from app.dependencies import get_current_user
from app.models.subscription import SubscriptionPlan, UserSubscription
from app.models.payment import PaymentTransaction
from app.services.razorpay_service import create_order, verify_payment_signature, verify_webhook_signature
from app.services.s3_service import get_s3_client
from app.services.points_service import award_referral_bonus
from app.services.settings_service import get_setting
from app.config import get_settings

router = APIRouter(prefix="/subscriptions", tags=["subscription"])
templates = Jinja2Templates(directory="app/templates")
settings = get_settings()


def _maybe_award_referral_bonus(user_id, db: Session):
    """Award plan-based referral bonus to referrer on referee's first subscription."""
    from app.models.user import User
    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.referred_by or user.referral_bonus_paid:
        return
    sub_count = db.query(UserSubscription).filter(UserSubscription.user_id == user_id).count()
    if sub_count <= 1:
        # Get bonus points from the plan the referee just subscribed to
        active_sub = db.query(UserSubscription).filter(
            UserSubscription.user_id == user_id,
            UserSubscription.status == "active",
        ).order_by(UserSubscription.created_at.desc()).first()
        bonus_pts = active_sub.plan.referral_bonus_points if active_sub else settings.REFERRAL_BONUS_POINTS
        try:
            award_referral_bonus(user.referred_by, user.full_name or user.email, db,
                                 bonus_points=bonus_pts)
        except Exception as e:
            logger.error(f"Referral bonus award failed: {e}")
        user.referral_bonus_paid = True
        db.commit()


def _upload_screenshot_to_s3(file: UploadFile) -> str:
    """Upload payment screenshot directly to S3, return key."""
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else "jpg"
    key = f"payment_screenshots/{datetime.utcnow().year}/{datetime.utcnow().month:02d}/{uuid.uuid4().hex}.{ext}"
    client = get_s3_client()
    client.upload_fileobj(
        file.file,
        settings.AWS_S3_BUCKET,
        key,
        ExtraArgs={"ContentType": file.content_type or "image/jpeg"},
    )
    return key


@router.get("/plans", response_class=HTMLResponse)
async def plans_page(request: Request, db: Session = Depends(get_db)):
    from app.dependencies import get_current_user_optional
    current_user = get_current_user_optional(request, db)

    plans = db.query(SubscriptionPlan).filter(SubscriptionPlan.is_active == True).order_by(SubscriptionPlan.price_inr).all()
    active_sub = None
    if current_user:
        active_sub = db.query(UserSubscription).filter(
            UserSubscription.user_id == current_user.id,
            UserSubscription.status == "active",
            UserSubscription.expires_at > datetime.utcnow(),
        ).first()

    razorpay_enabled = bool(settings.RAZORPAY_KEY_ID and settings.RAZORPAY_KEY_ID != "rzp_test_placeholder")

    return templates.TemplateResponse("subscription/plans.html", {
        "request": request,
        "user": current_user,
        "plans": plans,
        "active_sub": active_sub,
        "razorpay_key": settings.RAZORPAY_KEY_ID if razorpay_enabled else "",
        "razorpay_enabled": razorpay_enabled,
    })


# ── Razorpay flow ─────────────────────────────────────────────────────────────

@router.post("/create-order")
async def create_payment_order(
    request: Request,
    plan_id: str = Form(...),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == plan_id, SubscriptionPlan.is_active == True).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    if not settings.RAZORPAY_KEY_ID or settings.RAZORPAY_KEY_ID == "rzp_test_placeholder":
        raise HTTPException(status_code=503, detail="Razorpay not configured. Please use Manual Payment.")

    try:
        order_data = create_order(plan.price_inr, str(current_user.id), str(plan.id))
    except Exception as e:
        logger.error(f"Razorpay order creation failed: {e}")
        raise HTTPException(status_code=502, detail="Payment gateway error. Please use Manual Payment.")

    txn = PaymentTransaction(
        user_id=current_user.id,
        plan_id=plan.id,
        payment_method="razorpay",
        razorpay_order_id=order_data["order_id"],
        amount_inr=plan.price_inr,
        status="created",
    )
    db.add(txn)
    db.commit()

    return JSONResponse({
        "order_id": order_data["order_id"],
        "key": order_data["key"],
        "amount": order_data["amount"],
        "currency": order_data["currency"],
        "plan_id": str(plan.id),
        "plan_name": plan.display_name,
        "user_name": current_user.full_name,
        "user_email": current_user.email,
    })


@router.post("/verify")
async def verify_payment(
    request: Request,
    razorpay_order_id: str = Form(...),
    razorpay_payment_id: str = Form(...),
    razorpay_signature: str = Form(...),
    plan_id: str = Form(...),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not verify_payment_signature(razorpay_order_id, razorpay_payment_id, razorpay_signature):
        raise HTTPException(status_code=400, detail="Invalid payment signature")

    existing = db.query(UserSubscription).filter(
        UserSubscription.user_id == current_user.id,
        UserSubscription.razorpay_payment_id == razorpay_payment_id,
    ).first()
    if existing:
        return RedirectResponse(url="/subscriptions/success", status_code=302)

    plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    db.query(UserSubscription).filter(
        UserSubscription.user_id == current_user.id,
        UserSubscription.status == "active",
    ).update({"status": "expired"})

    sub = UserSubscription(
        user_id=current_user.id,
        plan_id=plan.id,
        status="active",
        razorpay_order_id=razorpay_order_id,
        razorpay_payment_id=razorpay_payment_id,
        started_at=datetime.utcnow(),
        expires_at=datetime.utcnow() + timedelta(days=plan.duration_days),
    )
    db.add(sub)

    txn = db.query(PaymentTransaction).filter(
        PaymentTransaction.razorpay_order_id == razorpay_order_id
    ).first()
    if txn:
        txn.razorpay_payment_id = razorpay_payment_id
        txn.razorpay_signature = razorpay_signature
        txn.status = "paid"
        txn.subscription_id = sub.id

    db.commit()
    _maybe_award_referral_bonus(current_user.id, db)
    return RedirectResponse(url="/subscriptions/success", status_code=302)


@router.post("/webhook")
async def razorpay_webhook(request: Request, db: Session = Depends(get_db)):
    body = await request.body()
    signature = request.headers.get("X-Razorpay-Signature", "")

    if not verify_webhook_signature(body, signature):
        raise HTTPException(status_code=400, detail="Invalid webhook signature")

    event = json.loads(body)
    if event.get("event") != "payment.captured":
        return JSONResponse({"status": "ignored"})

    payment = event["payload"]["payment"]["entity"]
    order_id = payment.get("order_id")
    payment_id = payment.get("id")
    notes = payment.get("notes", {})
    user_id = notes.get("user_id")
    plan_id = notes.get("plan_id")

    if not all([order_id, payment_id, user_id, plan_id]):
        return JSONResponse({"status": "missing data"})

    existing = db.query(UserSubscription).filter(
        UserSubscription.razorpay_payment_id == payment_id
    ).first()
    if existing:
        return JSONResponse({"status": "already processed"})

    plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == plan_id).first()
    if not plan:
        return JSONResponse({"status": "plan not found"})

    db.query(UserSubscription).filter(
        UserSubscription.user_id == user_id,
        UserSubscription.status == "active",
    ).update({"status": "expired"})

    sub = UserSubscription(
        user_id=user_id,
        plan_id=plan.id,
        status="active",
        razorpay_order_id=order_id,
        razorpay_payment_id=payment_id,
        started_at=datetime.utcnow(),
        expires_at=datetime.utcnow() + timedelta(days=plan.duration_days),
    )
    db.add(sub)

    txn = db.query(PaymentTransaction).filter(
        PaymentTransaction.razorpay_order_id == order_id
    ).first()
    if txn:
        txn.razorpay_payment_id = payment_id
        txn.status = "paid"
        txn.subscription_id = sub.id

    db.commit()
    _maybe_award_referral_bonus(user_id, db)
    return JSONResponse({"status": "ok"})


# ── Manual payment flow ───────────────────────────────────────────────────────

@router.get("/manual/{plan_id}", response_class=HTMLResponse)
async def manual_payment_page(
    request: Request,
    plan_id: str,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == plan_id, SubscriptionPlan.is_active == True).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    return templates.TemplateResponse("subscription/manual_payment.html", {
        "request": request,
        "user": current_user,
        "plan": plan,
        "upi_id": get_setting("manual_upi_id", db) or settings.MANUAL_UPI_ID,
        "bank_name": get_setting("manual_bank_name", db) or settings.MANUAL_BANK_NAME,
        "bank_account": get_setting("manual_bank_account", db) or settings.MANUAL_BANK_ACCOUNT,
        "bank_ifsc": get_setting("manual_bank_ifsc", db) or settings.MANUAL_BANK_IFSC,
        "account_name": get_setting("manual_account_name", db) or settings.MANUAL_ACCOUNT_NAME,
    })


@router.post("/manual/{plan_id}")
async def submit_manual_payment(
    request: Request,
    plan_id: str,
    transaction_id: str = Form(...),
    screenshot: UploadFile = File(...),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == plan_id, SubscriptionPlan.is_active == True).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    # Check no pending manual payment already
    existing_pending = db.query(PaymentTransaction).filter(
        PaymentTransaction.user_id == current_user.id,
        PaymentTransaction.payment_method == "manual",
        PaymentTransaction.status == "pending_verification",
    ).first()
    if existing_pending:
        return templates.TemplateResponse("subscription/manual_payment.html", {
            "request": request,
            "user": current_user,
            "plan": plan,
            "upi_id": get_setting("manual_upi_id", db) or settings.MANUAL_UPI_ID,
            "bank_name": get_setting("manual_bank_name", db) or settings.MANUAL_BANK_NAME,
            "bank_account": get_setting("manual_bank_account", db) or settings.MANUAL_BANK_ACCOUNT,
            "bank_ifsc": get_setting("manual_bank_ifsc", db) or settings.MANUAL_BANK_IFSC,
            "account_name": get_setting("manual_account_name", db) or settings.MANUAL_ACCOUNT_NAME,
            "error": "You already have a pending payment verification. Please wait for admin approval.",
        }, status_code=400)

    # Validate screenshot file type
    allowed_types = ["image/jpeg", "image/png", "image/webp", "image/jpg"]
    if screenshot.content_type not in allowed_types:
        return templates.TemplateResponse("subscription/manual_payment.html", {
            "request": request,
            "user": current_user,
            "plan": plan,
            "upi_id": get_setting("manual_upi_id", db) or settings.MANUAL_UPI_ID,
            "bank_name": get_setting("manual_bank_name", db) or settings.MANUAL_BANK_NAME,
            "bank_account": get_setting("manual_bank_account", db) or settings.MANUAL_BANK_ACCOUNT,
            "bank_ifsc": get_setting("manual_bank_ifsc", db) or settings.MANUAL_BANK_IFSC,
            "account_name": get_setting("manual_account_name", db) or settings.MANUAL_ACCOUNT_NAME,
            "error": "Screenshot must be a JPG, PNG, or WebP image.",
        }, status_code=400)

    # Upload screenshot to S3
    screenshot_key = None
    try:
        screenshot_key = _upload_screenshot_to_s3(screenshot)
    except Exception as e:
        logger.error(f"Screenshot upload failed: {e}")
        # Allow submission without screenshot if S3 not configured
        screenshot_key = None

    txn = PaymentTransaction(
        user_id=current_user.id,
        plan_id=plan.id,
        payment_method="manual",
        razorpay_order_id=f"manual_{uuid.uuid4().hex[:16]}",  # unique placeholder
        manual_transaction_id=transaction_id.strip(),
        manual_screenshot_url=screenshot_key,
        amount_inr=plan.price_inr,
        status="pending_verification",
    )
    db.add(txn)
    db.commit()

    return RedirectResponse(url="/subscriptions/manual-pending", status_code=302)


@router.get("/manual-pending", response_class=HTMLResponse)
async def manual_pending_page(
    request: Request,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    pending = db.query(PaymentTransaction).filter(
        PaymentTransaction.user_id == current_user.id,
        PaymentTransaction.payment_method == "manual",
    ).order_by(PaymentTransaction.created_at.desc()).first()

    return templates.TemplateResponse("subscription/manual_pending.html", {
        "request": request,
        "user": current_user,
        "transaction": pending,
    })


# ── Success page ──────────────────────────────────────────────────────────────

@router.get("/success", response_class=HTMLResponse)
async def payment_success(request: Request, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    sub = db.query(UserSubscription).filter(
        UserSubscription.user_id == current_user.id,
        UserSubscription.status == "active",
    ).order_by(UserSubscription.created_at.desc()).first()
    return templates.TemplateResponse("subscription/payment_success.html", {
        "request": request,
        "user": current_user,
        "subscription": sub,
    })
