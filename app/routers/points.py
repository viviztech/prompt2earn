from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.dependencies import get_current_user
from app.models.points import PointsLedger
from app.models.user import User
from app.services.points_service import get_balance, get_leaderboard
from app.config import get_settings

router = APIRouter(tags=["points"])
templates = Jinja2Templates(directory="app/templates")
settings = get_settings()


@router.get("/wallet", response_class=HTMLResponse)
async def wallet(
    request: Request,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    balance = get_balance(current_user.id, db)
    history = (
        db.query(PointsLedger)
        .filter(PointsLedger.user_id == current_user.id)
        .order_by(PointsLedger.created_at.desc())
        .limit(50)
        .all()
    )
    earned_total = db.query(func.sum(PointsLedger.points)).filter(
        PointsLedger.user_id == current_user.id,
        PointsLedger.points > 0,
    ).scalar() or 0

    referral_bonus_total = db.query(func.sum(PointsLedger.points)).filter(
        PointsLedger.user_id == current_user.id,
        PointsLedger.transaction_type == "bonus",
    ).scalar() or 0

    referral_count = db.query(User).filter(User.referred_by == current_user.id).count()

    return templates.TemplateResponse("user/wallet.html", {
        "request": request,
        "user": current_user,
        "balance": balance,
        "history": history,
        "earned_total": earned_total,
        "referral_bonus_total": referral_bonus_total,
        "referral_count": referral_count,
    })


@router.get("/leaderboard", response_class=HTMLResponse)
async def leaderboard(
    request: Request,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    top_users = get_leaderboard(db, limit=20)
    return templates.TemplateResponse("user/leaderboard.html", {
        "request": request,
        "user": current_user,
        "top_users": top_users,
    })


@router.get("/referral", response_class=HTMLResponse)
async def referral_page(
    request: Request,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Referrals made by this user
    referrals = db.query(User).filter(User.referred_by == current_user.id).order_by(User.created_at.desc()).all()

    # Total bonus points earned from referrals
    bonus_earned = db.query(func.sum(PointsLedger.points)).filter(
        PointsLedger.user_id == current_user.id,
        PointsLedger.transaction_type == "bonus",
    ).scalar() or 0

    referral_link = f"{settings.BASE_URL}/auth/register?ref={current_user.referral_code}"

    return templates.TemplateResponse("user/referral.html", {
        "request": request,
        "user": current_user,
        "referrals": referrals,
        "bonus_earned": bonus_earned,
        "referral_link": referral_link,
        "bonus_per_referral": settings.REFERRAL_BONUS_POINTS,
    })


@router.get("/api/wallet/balance")
async def wallet_balance(
    request: Request,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    balance = get_balance(current_user.id, db)
    return JSONResponse({"balance": balance})


@router.get("/api/leaderboard/data")
async def leaderboard_data(
    request: Request,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    top_users = get_leaderboard(db, limit=10)
    return JSONResponse({"leaderboard": top_users})
