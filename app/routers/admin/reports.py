from datetime import datetime, timedelta
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func, extract

from app.database import get_db
from app.dependencies import require_admin
from app.models.payment import PaymentTransaction
from app.models.points import PointsLedger
from app.models.user import User
from app.models.submission import Submission

router = APIRouter(tags=["admin"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/reports", response_class=HTMLResponse)
async def reports(
    request: Request,
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    now = datetime.utcnow()

    monthly_revenue = []
    for i in range(6):
        month = (now.month - i - 1) % 12 + 1
        year = now.year if now.month - i > 0 else now.year - 1
        revenue = db.query(func.sum(PaymentTransaction.amount_inr)).filter(
            PaymentTransaction.status == "paid",
            extract("month", PaymentTransaction.created_at) == month,
            extract("year", PaymentTransaction.created_at) == year,
        ).scalar() or 0
        monthly_revenue.append({"month": f"{year}-{month:02d}", "revenue": float(revenue)})
    monthly_revenue.reverse()

    total_revenue = db.query(func.sum(PaymentTransaction.amount_inr)).filter(
        PaymentTransaction.status == "paid"
    ).scalar() or 0
    total_points_awarded = db.query(func.sum(PointsLedger.points)).filter(
        PointsLedger.transaction_type == "earned"
    ).scalar() or 0
    total_redeemed = db.query(func.sum(PointsLedger.points)).filter(
        PointsLedger.transaction_type == "redeemed"
    ).scalar() or 0
    total_users = db.query(func.count(User.id)).filter(User.role == "user").scalar()
    total_submissions = db.query(func.count(Submission.id)).scalar()

    return templates.TemplateResponse("admin/reports.html", {
        "request": request,
        "user": current_user,
        "monthly_revenue": monthly_revenue,
        "total_revenue": total_revenue,
        "total_points_awarded": total_points_awarded,
        "total_redeemed": abs(total_redeemed or 0),
        "total_users": total_users,
        "total_submissions": total_submissions,
    })
