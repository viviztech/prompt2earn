from datetime import datetime, timedelta
from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.dependencies import require_admin

settings = get_settings()
from app.models.payment import PaymentTransaction
from app.models.subscription import UserSubscription, SubscriptionPlan
from app.services.s3_service import create_presigned_get_url
from app.services.points_service import award_referral_bonus

router = APIRouter(tags=["admin"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/payments", response_class=HTMLResponse)
async def list_manual_payments(
    request: Request,
    status: str = "pending_verification",
    page: int = 1,
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    page_size = 20
    offset = (page - 1) * page_size
    query = db.query(PaymentTransaction).filter(PaymentTransaction.payment_method == "manual")
    if status in ["pending_verification", "paid", "rejected"]:
        query = query.filter(PaymentTransaction.status == status)
    transactions = query.order_by(PaymentTransaction.created_at.asc()).offset(offset).limit(page_size).all()
    total = query.count()
    return templates.TemplateResponse("admin/payments.html", {
        "request": request,
        "user": current_user,
        "transactions": transactions,
        "status_filter": status,
        "page": page,
        "total_pages": (total + page_size - 1) // page_size,
    })


@router.get("/payments/{txn_id}", response_class=HTMLResponse)
async def view_manual_payment(
    request: Request,
    txn_id: str,
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    txn = db.query(PaymentTransaction).filter(PaymentTransaction.id == txn_id).first()
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found")
    screenshot_url = create_presigned_get_url(txn.manual_screenshot_url) if txn.manual_screenshot_url else None
    return templates.TemplateResponse("admin/payment_review.html", {
        "request": request,
        "user": current_user,
        "txn": txn,
        "screenshot_url": screenshot_url,
    })


@router.post("/payments/{txn_id}/approve")
async def approve_manual_payment(
    request: Request,
    txn_id: str,
    admin_note: str = Form(default="Approved"),
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    txn = db.query(PaymentTransaction).filter(PaymentTransaction.id == txn_id).first()
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found")
    if txn.status != "pending_verification":
        raise HTTPException(status_code=400, detail="Already processed")

    plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == txn.plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    # Expire existing active subscriptions
    db.query(UserSubscription).filter(
        UserSubscription.user_id == txn.user_id,
        UserSubscription.status == "active",
    ).update({"status": "expired"})

    sub = UserSubscription(
        user_id=txn.user_id,
        plan_id=plan.id,
        status="active",
        started_at=datetime.utcnow(),
        expires_at=datetime.utcnow() + timedelta(days=plan.duration_days),
    )
    db.add(sub)
    db.flush()

    txn.status = "paid"
    txn.admin_note = admin_note
    txn.reviewed_by = current_user.id
    txn.reviewed_at = datetime.utcnow()
    txn.subscription_id = sub.id
    db.commit()

    # Award referral bonus to referrer if applicable
    from app.models.user import User
    user = db.query(User).filter(User.id == txn.user_id).first()
    if user and user.referred_by and not user.referral_bonus_paid:
        sub_count = db.query(UserSubscription).filter(UserSubscription.user_id == user.id).count()
        if sub_count <= 1:
            bonus_pts = plan.referral_bonus_points if plan else settings.REFERRAL_BONUS_POINTS
            try:
                award_referral_bonus(user.referred_by, user.full_name or user.email, db,
                                     bonus_points=bonus_pts)
            except Exception:
                pass
            user.referral_bonus_paid = True
            db.commit()

    return RedirectResponse(url="/admin/payments?status=pending_verification", status_code=302)


@router.post("/payments/{txn_id}/reject")
async def reject_manual_payment(
    request: Request,
    txn_id: str,
    admin_note: str = Form(...),
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    txn = db.query(PaymentTransaction).filter(PaymentTransaction.id == txn_id).first()
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found")
    if txn.status != "pending_verification":
        raise HTTPException(status_code=400, detail="Already processed")

    txn.status = "rejected"
    txn.admin_note = admin_note
    txn.reviewed_by = current_user.id
    txn.reviewed_at = datetime.utcnow()
    db.commit()

    return RedirectResponse(url="/admin/payments?status=pending_verification", status_code=302)
