from datetime import datetime
from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.prompt import Prompt
from app.models.submission import Submission
from app.models.subscription import UserSubscription
from app.services.points_service import get_balance

router = APIRouter(tags=["user"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    active_sub = db.query(UserSubscription).filter(
        UserSubscription.user_id == current_user.id,
        UserSubscription.status == "active",
        UserSubscription.expires_at > datetime.utcnow(),
    ).first()

    if not active_sub:
        return RedirectResponse(url="/subscriptions/plans", status_code=302)

    plan_name = active_sub.plan.name
    now = datetime.utcnow()

    from sqlalchemy import or_
    prompts = db.query(Prompt).filter(
        Prompt.is_active == True,
        Prompt.deadline > now,
        Prompt.visible_to.contains([plan_name]),
        or_(Prompt.assigned_to == None, Prompt.assigned_to == current_user.id),
    ).order_by(Prompt.deadline.asc()).all()

    submitted_ids = {
        s.prompt_id for s in db.query(Submission.prompt_id).filter(
            Submission.user_id == current_user.id
        ).all()
    }

    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_count = db.query(Submission).filter(
        Submission.user_id == current_user.id,
        Submission.submitted_at >= today_start,
    ).count()

    balance = get_balance(current_user.id, db)

    return templates.TemplateResponse("user/dashboard.html", {
        "request": request,
        "user": current_user,
        "prompts": prompts,
        "submitted_ids": submitted_ids,
        "active_sub": active_sub,
        "balance": balance,
        "today_count": today_count,
    })


@router.get("/profile", response_class=HTMLResponse)
async def profile_page(
    request: Request,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    active_sub = db.query(UserSubscription).filter(
        UserSubscription.user_id == current_user.id,
        UserSubscription.status == "active",
        UserSubscription.expires_at > datetime.utcnow(),
    ).first()
    balance = get_balance(current_user.id, db)
    total_submissions = db.query(Submission).filter(Submission.user_id == current_user.id).count()
    approved_submissions = db.query(Submission).filter(
        Submission.user_id == current_user.id,
        Submission.status == "approved",
    ).count()
    referral_count = db.query(Submission).filter(
        Submission.user_id == current_user.id,
    ).count()
    from app.models.user import User
    referral_count = db.query(User).filter(User.referred_by == current_user.id).count()
    return templates.TemplateResponse("user/profile.html", {
        "request": request,
        "user": current_user,
        "active_sub": active_sub,
        "balance": balance,
        "total_submissions": total_submissions,
        "approved_submissions": approved_submissions,
        "referral_count": referral_count,
    })


@router.post("/profile/update")
async def update_profile(
    request: Request,
    full_name: str = Form(...),
    phone: str = Form(...),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    current_user.full_name = full_name.strip()
    current_user.phone = phone.strip()
    db.commit()
    return RedirectResponse(url="/profile?updated=1", status_code=302)
