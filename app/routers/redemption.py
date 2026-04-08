from datetime import datetime
from decimal import Decimal
from fastapi import APIRouter, Request, Depends, HTTPException, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.redemption import RedemptionRequest
from app.models.points import PointsLedger
from app.services.points_service import get_balance, deduct_points
from app.config import get_settings

router = APIRouter(tags=["redemption"])
templates = Jinja2Templates(directory="app/templates")
settings = get_settings()


@router.get("/redeem", response_class=HTMLResponse)
async def redeem_page(
    request: Request,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    balance = get_balance(current_user.id, db)
    pending_requests = db.query(RedemptionRequest).filter(
        RedemptionRequest.user_id == current_user.id,
        RedemptionRequest.status.in_(["pending", "processing"]),
    ).count()

    history = db.query(RedemptionRequest).filter(
        RedemptionRequest.user_id == current_user.id,
    ).order_by(RedemptionRequest.created_at.desc()).limit(10).all()

    return templates.TemplateResponse("user/redeem.html", {
        "request": request,
        "user": current_user,
        "balance": balance,
        "min_points": settings.MINIMUM_REDEMPTION_POINTS,
        "pending_requests": pending_requests,
        "history": history,
    })


@router.post("/redeem")
async def submit_redemption(
    request: Request,
    points_requested: int = Form(...),
    payment_method: str = Form(...),
    bank_account_number: str = Form(None),
    bank_ifsc: str = Form(None),
    bank_account_name: str = Form(None),
    upi_id: str = Form(None),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    balance = get_balance(current_user.id, db)
    errors = []

    if points_requested < settings.MINIMUM_REDEMPTION_POINTS:
        errors.append(f"Minimum redemption is {settings.MINIMUM_REDEMPTION_POINTS} points.")
    if points_requested > balance:
        errors.append("Insufficient points balance.")
    if payment_method == "bank_transfer" and not all([bank_account_number, bank_ifsc, bank_account_name]):
        errors.append("Bank account details are required for bank transfer.")
    if payment_method == "upi" and not upi_id:
        errors.append("UPI ID is required.")

    # Check no pending request
    existing = db.query(RedemptionRequest).filter(
        RedemptionRequest.user_id == current_user.id,
        RedemptionRequest.status.in_(["pending", "processing"]),
    ).first()
    if existing:
        errors.append("You already have a pending redemption request.")

    if errors:
        history = db.query(RedemptionRequest).filter(
            RedemptionRequest.user_id == current_user.id,
        ).order_by(RedemptionRequest.created_at.desc()).limit(10).all()
        return templates.TemplateResponse("user/redeem.html", {
            "request": request,
            "user": current_user,
            "balance": balance,
            "min_points": settings.MINIMUM_REDEMPTION_POINTS,
            "errors": errors,
            "history": history,
            "pending_requests": 0,
        }, status_code=400)

    amount_inr = Decimal(points_requested) / settings.POINTS_PER_INR

    redemption = RedemptionRequest(
        user_id=current_user.id,
        points_requested=points_requested,
        amount_inr=amount_inr,
        payment_method=payment_method,
        bank_account_number=bank_account_number,
        bank_ifsc=bank_ifsc,
        bank_account_name=bank_account_name,
        upi_id=upi_id,
        status="pending",
    )
    db.add(redemption)
    db.flush()  # Get ID before deduct

    deduct_points(current_user.id, redemption.id, points_requested, db)
    db.commit()

    return RedirectResponse(url="/redeem?success=1", status_code=302)
