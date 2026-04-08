from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_admin
from app.models.user import User
from app.models.submission import Submission
from app.services.points_service import get_balance

router = APIRouter(tags=["admin"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/users", response_class=HTMLResponse)
async def list_users(
    request: Request,
    page: int = 1,
    search: str = "",
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    page_size = 25
    offset = (page - 1) * page_size
    query = db.query(User).filter(User.role == "user")
    if search:
        query = query.filter(
            (User.email.ilike(f"%{search}%")) | (User.full_name.ilike(f"%{search}%"))
        )
    users = query.order_by(User.created_at.desc()).offset(offset).limit(page_size).all()
    total = query.count()
    return templates.TemplateResponse("admin/users.html", {
        "request": request,
        "user": current_user,
        "users": users,
        "search": search,
        "page": page,
        "total_pages": (total + page_size - 1) // page_size,
    })


@router.get("/users/{user_id}", response_class=HTMLResponse)
async def view_user(
    request: Request,
    user_id: str,
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    balance = get_balance(user_id, db)
    submissions = db.query(Submission).filter(Submission.user_id == user_id).order_by(Submission.submitted_at.desc()).limit(20).all()
    return templates.TemplateResponse("admin/user_detail.html", {
        "request": request,
        "user": current_user,
        "target_user": target,
        "balance": balance,
        "submissions": submissions,
    })


@router.post("/users/{user_id}/suspend")
async def suspend_user(
    request: Request,
    user_id: str,
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    target.is_suspended = True
    db.commit()
    return RedirectResponse(url=f"/admin/users/{user_id}", status_code=302)


@router.post("/users/{user_id}/activate")
async def activate_user(
    request: Request,
    user_id: str,
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    target.is_suspended = False
    db.commit()
    return RedirectResponse(url=f"/admin/users/{user_id}", status_code=302)
