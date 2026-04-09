from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from decimal import Decimal

from app.database import get_db
from app.dependencies import require_admin
from app.models.subscription import SubscriptionPlan

router = APIRouter(tags=["admin"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/plans", response_class=HTMLResponse)
async def list_plans(
    request: Request,
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    plans = db.query(SubscriptionPlan).order_by(SubscriptionPlan.price_inr).all()
    return templates.TemplateResponse("admin/plans.html", {
        "request": request,
        "user": current_user,
        "plans": plans,
        "saved": request.query_params.get("saved"),
    })


@router.post("/plans/{plan_id}/update")
async def update_plan(
    request: Request,
    plan_id: str,
    display_name: str = Form(...),
    price_inr: str = Form(...),
    duration_days: int = Form(...),
    point_multiplier: str = Form(...),
    max_daily_submissions: int = Form(...),
    referral_bonus_points: int = Form(...),
    daily_completion_bonus: int = Form(...),
    company_profit_pct: str = Form(...),
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == plan_id).first()
    if plan:
        plan.display_name = display_name
        plan.price_inr = Decimal(price_inr)
        plan.duration_days = duration_days
        plan.point_multiplier = Decimal(point_multiplier)
        plan.max_daily_submissions = max_daily_submissions
        plan.referral_bonus_points = referral_bonus_points
        plan.daily_completion_bonus = daily_completion_bonus
        plan.company_profit_pct = Decimal(company_profit_pct)
        db.commit()
    return RedirectResponse(url="/admin/plans?saved=1", status_code=302)
