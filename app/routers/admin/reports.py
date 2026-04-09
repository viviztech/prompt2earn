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
from app.models.subscription import UserSubscription, SubscriptionPlan
from app.models.redemption import RedemptionRequest

router = APIRouter(tags=["admin"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/reports", response_class=HTMLResponse)
async def reports(
    request: Request,
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    now = datetime.utcnow()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    last_month_start = (month_start - timedelta(days=1)).replace(day=1)

    # ── Revenue ────────────────────────────────────────────────────────────────
    total_revenue = float(db.query(func.sum(PaymentTransaction.amount_inr)).filter(
        PaymentTransaction.status == "paid"
    ).scalar() or 0)

    this_month_revenue = float(db.query(func.sum(PaymentTransaction.amount_inr)).filter(
        PaymentTransaction.status == "paid",
        PaymentTransaction.created_at >= month_start,
    ).scalar() or 0)

    last_month_revenue = float(db.query(func.sum(PaymentTransaction.amount_inr)).filter(
        PaymentTransaction.status == "paid",
        PaymentTransaction.created_at >= last_month_start,
        PaymentTransaction.created_at < month_start,
    ).scalar() or 0)

    # ── Economics: 20% company profit, 80% user pool ──────────────────────────
    company_profit_this_month = round(this_month_revenue * 0.20, 2)
    user_pool_this_month = round(this_month_revenue * 0.80, 2)
    company_profit_total = round(total_revenue * 0.20, 2)
    user_pool_total = round(total_revenue * 0.80, 2)

    # ── Points / Payouts ───────────────────────────────────────────────────────
    total_points_awarded = int(db.query(func.sum(PointsLedger.points)).filter(
        PointsLedger.points > 0
    ).scalar() or 0)

    total_bonus_points = int(db.query(func.sum(PointsLedger.points)).filter(
        PointsLedger.transaction_type == "bonus",
    ).scalar() or 0)

    total_redeemed_pts = abs(int(db.query(func.sum(PointsLedger.points)).filter(
        PointsLedger.transaction_type == "redeemed"
    ).scalar() or 0))

    # Actual cash paid out (completed redemptions)
    total_paid_out = float(db.query(func.sum(RedemptionRequest.amount_inr)).filter(
        RedemptionRequest.status == "completed"
    ).scalar() or 0)

    pending_payout = float(db.query(func.sum(RedemptionRequest.amount_inr)).filter(
        RedemptionRequest.status.in_(["pending", "processing"])
    ).scalar() or 0)

    # Unredeemed points still in system (potential liability)
    unredeemed_pts = total_points_awarded - total_redeemed_pts
    unredeemed_inr = max(0, unredeemed_pts)  # 1pt = ₹1

    # Net margin = total revenue - actual paid out
    net_margin = round(total_revenue - total_paid_out, 2)
    net_margin_pct = round((net_margin / total_revenue * 100) if total_revenue else 0, 1)

    # ── Users & Subscriptions ─────────────────────────────────────────────────
    total_users = db.query(func.count(User.id)).filter(User.role == "user").scalar() or 0
    new_users_this_month = db.query(func.count(User.id)).filter(
        User.role == "user",
        User.created_at >= month_start,
    ).scalar() or 0

    active_subs = db.query(func.count(UserSubscription.id)).filter(
        UserSubscription.status == "active",
        UserSubscription.expires_at > now,
    ).scalar() or 0

    # Subs by plan
    plan_counts = db.query(
        SubscriptionPlan.display_name,
        SubscriptionPlan.price_inr,
        func.count(UserSubscription.id).label("count"),
    ).join(UserSubscription, SubscriptionPlan.id == UserSubscription.plan_id).filter(
        UserSubscription.status == "active",
        UserSubscription.expires_at > now,
    ).group_by(SubscriptionPlan.display_name, SubscriptionPlan.price_inr).all()

    plan_breakdown = [
        {
            "name": r.display_name,
            "price": float(r.price_inr),
            "count": r.count,
            "mrr": float(r.price_inr) * r.count,
            "profit": round(float(r.price_inr) * r.count * 0.20, 2),
        }
        for r in plan_counts
    ]
    mrr = sum(p["mrr"] for p in plan_breakdown)

    # ── Submissions ────────────────────────────────────────────────────────────
    total_submissions = db.query(func.count(Submission.id)).scalar() or 0
    approved_submissions = db.query(func.count(Submission.id)).filter(
        Submission.status == "approved"
    ).scalar() or 0
    approval_rate = round(approved_submissions / total_submissions * 100, 1) if total_submissions else 0

    this_month_submissions = db.query(func.count(Submission.id)).filter(
        Submission.submitted_at >= month_start,
    ).scalar() or 0

    # ── Monthly trend (last 6 months) ─────────────────────────────────────────
    monthly_trend = []
    for i in range(5, -1, -1):
        dt = now - timedelta(days=30 * i)
        m, y = dt.month, dt.year
        rev = float(db.query(func.sum(PaymentTransaction.amount_inr)).filter(
            PaymentTransaction.status == "paid",
            extract("month", PaymentTransaction.created_at) == m,
            extract("year", PaymentTransaction.created_at) == y,
        ).scalar() or 0)
        subs_count = db.query(func.count(UserSubscription.id)).filter(
            extract("month", UserSubscription.created_at) == m,
            extract("year", UserSubscription.created_at) == y,
        ).scalar() or 0
        monthly_trend.append({
            "label": dt.strftime("%b %Y"),
            "revenue": rev,
            "profit": round(rev * 0.20, 2),
            "subs": subs_count,
        })

    return templates.TemplateResponse("admin/reports.html", {
        "active_nav": "reports",
        "request": request,
        "user": current_user,
        # Revenue
        "total_revenue": total_revenue,
        "this_month_revenue": this_month_revenue,
        "last_month_revenue": last_month_revenue,
        "mrr": mrr,
        # Economics
        "company_profit_this_month": company_profit_this_month,
        "user_pool_this_month": user_pool_this_month,
        "company_profit_total": company_profit_total,
        "user_pool_total": user_pool_total,
        "net_margin": net_margin,
        "net_margin_pct": net_margin_pct,
        # Points / payouts
        "total_points_awarded": total_points_awarded,
        "total_bonus_points": total_bonus_points,
        "total_redeemed_pts": total_redeemed_pts,
        "total_paid_out": total_paid_out,
        "pending_payout": pending_payout,
        "unredeemed_inr": unredeemed_inr,
        # Users
        "total_users": total_users,
        "new_users_this_month": new_users_this_month,
        "active_subs": active_subs,
        "plan_breakdown": plan_breakdown,
        # Submissions
        "total_submissions": total_submissions,
        "approved_submissions": approved_submissions,
        "approval_rate": approval_rate,
        "this_month_submissions": this_month_submissions,
        # Trend
        "monthly_trend": monthly_trend,
    })
