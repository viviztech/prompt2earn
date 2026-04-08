from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.points import PointsLedger
from app.services.points_service import get_balance, get_leaderboard

router = APIRouter(tags=["points"])
templates = Jinja2Templates(directory="app/templates")


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
    return templates.TemplateResponse("user/wallet.html", {
        "request": request,
        "user": current_user,
        "balance": balance,
        "history": history,
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
