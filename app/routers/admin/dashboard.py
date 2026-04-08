from datetime import datetime, timedelta
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.dependencies import require_admin
from app.models.user import User
from app.models.submission import Submission
from app.models.points import PointsLedger
from app.models.payment import PaymentTransaction
from app.models.redemption import RedemptionRequest

router = APIRouter(tags=["admin"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/dashboard", response_class=HTMLResponse)
async def admin_dashboard(
    request: Request,
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    total_users = db.query(func.count(User.id)).filter(User.role == "user").scalar()
    today_submissions = db.query(func.count(Submission.id)).filter(Submission.submitted_at >= today_start).scalar()
    pending_reviews = db.query(func.count(Submission.id)).filter(Submission.status == "pending").scalar()
    total_points_month = db.query(func.sum(PointsLedger.points)).filter(
        PointsLedger.transaction_type == "earned",
        PointsLedger.created_at >= month_start,
    ).scalar() or 0
    revenue_month = db.query(func.sum(PaymentTransaction.amount_inr)).filter(
        PaymentTransaction.status == "paid",
        PaymentTransaction.created_at >= month_start,
    ).scalar() or 0
    pending_redemptions = db.query(func.count(RedemptionRequest.id)).filter(
        RedemptionRequest.status.in_(["pending", "processing"])
    ).scalar()

    recent_submissions = db.query(Submission).order_by(Submission.submitted_at.desc()).limit(10).all()

    return templates.TemplateResponse("admin/dashboard.html", {
        "request": request,
        "user": current_user,
        "stats": {
            "total_users": total_users,
            "today_submissions": today_submissions,
            "pending_reviews": pending_reviews,
            "total_points_month": total_points_month,
            "revenue_month": revenue_month,
            "pending_redemptions": pending_redemptions,
        },
        "recent_submissions": recent_submissions,
    })
