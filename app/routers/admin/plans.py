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
    })


@router.post("/plans/{plan_id}/update")
async def update_plan(
    request: Request,
    plan_id: str,
    display_name: str = Form(...),
    price_inr: str = Form(...),
    duration_days: int = Form(...),
    point_multiplier: str = Form(...),
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == plan_id).first()
    if plan:
        plan.display_name = display_name
        plan.price_inr = Decimal(price_inr)
        plan.duration_days = duration_days
        plan.point_multiplier = Decimal(point_multiplier)
        db.commit()
    return RedirectResponse(url="/admin/plans", status_code=302)
