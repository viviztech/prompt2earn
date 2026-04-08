import json
from datetime import datetime, timedelta
from fastapi import APIRouter, Request, Depends, HTTPException, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.subscription import SubscriptionPlan, UserSubscription
from app.models.payment import PaymentTransaction
from app.services.razorpay_service import create_order, verify_payment_signature, verify_webhook_signature
from app.config import get_settings

router = APIRouter(prefix="/subscriptions", tags=["subscription"])
templates = Jinja2Templates(directory="app/templates")
settings = get_settings()


@router.get("/plans", response_class=HTMLResponse)
async def plans_page(request: Request, db: Session = Depends(get_db)):
    current_user = None
    try:
        current_user = get_current_user(request, db)
    except HTTPException:
        pass

    plans = db.query(SubscriptionPlan).filter(SubscriptionPlan.is_active == True).order_by(SubscriptionPlan.price_inr).all()
    active_sub = None
    if current_user:
        active_sub = db.query(UserSubscription).filter(
            UserSubscription.user_id == current_user.id,
            UserSubscription.status == "active",
            UserSubscription.expires_at > datetime.utcnow(),
        ).first()
    return templates.TemplateResponse("subscription/plans.html", {
        "request": request,
        "user": current_user,
        "plans": plans,
        "active_sub": active_sub,
        "razorpay_key": settings.RAZORPAY_KEY_ID,
    })


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

    order_data = create_order(plan.price_inr, str(current_user.id), str(plan.id))

    txn = PaymentTransaction(
        user_id=current_user.id,
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

    # Idempotency check
    existing = db.query(UserSubscription).filter(
        UserSubscription.user_id == current_user.id,
        UserSubscription.razorpay_payment_id == razorpay_payment_id,
    ).first()
    if existing:
        return RedirectResponse(url="/subscriptions/success", status_code=302)

    plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    # Expire old active subscriptions
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
    return JSONResponse({"status": "ok"})


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
