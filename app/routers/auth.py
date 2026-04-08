from datetime import datetime, timedelta
from fastapi import APIRouter, Request, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.database import get_db
from app.models.user import User
from app.services.auth_service import (
    hash_password, verify_password, generate_otp,
    create_access_token, create_refresh_token
)
from app.services.email_service import send_otp_email
from app.config import get_settings

router = APIRouter(prefix="/auth", tags=["auth"])
templates = Jinja2Templates(directory="app/templates")
settings = get_settings()
limiter = Limiter(key_func=get_remote_address)


@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse("auth/register.html", {"request": request})


@router.post("/register")
@limiter.limit("3/minute")
async def register(
    request: Request,
    full_name: str = Form(...),
    email: str = Form(...),
    phone: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    existing = db.query(User).filter(User.email == email.lower().strip()).first()
    if existing:
        return templates.TemplateResponse(
            "auth/register.html",
            {"request": request, "error": "Email already registered."},
            status_code=400,
        )

    otp = generate_otp()
    user = User(
        email=email.lower().strip(),
        password_hash=hash_password(password),
        full_name=full_name.strip(),
        phone=phone.strip(),
        otp_code=hash_password(otp),
        otp_expires_at=datetime.utcnow() + timedelta(minutes=10),
        is_verified=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    send_otp_email(user.email, otp, user.full_name)

    response = RedirectResponse(url="/auth/verify-otp", status_code=302)
    response.set_cookie("pending_user_id", str(user.id), max_age=600, httponly=True, samesite="lax")
    return response


@router.get("/verify-otp", response_class=HTMLResponse)
async def verify_otp_page(request: Request):
    return templates.TemplateResponse("auth/verify_otp.html", {"request": request})


@router.post("/verify-otp")
async def verify_otp(
    request: Request,
    otp: str = Form(...),
    db: Session = Depends(get_db),
):
    user_id = request.cookies.get("pending_user_id")
    if not user_id:
        return RedirectResponse(url="/auth/register", status_code=302)

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return RedirectResponse(url="/auth/register", status_code=302)

    if not user.otp_expires_at or datetime.utcnow() > user.otp_expires_at:
        return templates.TemplateResponse(
            "auth/verify_otp.html",
            {"request": request, "error": "OTP expired. Please request a new one."},
            status_code=400,
        )

    if not verify_password(otp, user.otp_code):
        return templates.TemplateResponse(
            "auth/verify_otp.html",
            {"request": request, "error": "Invalid OTP. Please try again."},
            status_code=400,
        )

    user.is_verified = True
    user.otp_code = None
    user.otp_expires_at = None
    db.commit()

    access_token = create_access_token(str(user.id))
    refresh_token = create_refresh_token(str(user.id))

    is_https = request.url.scheme == "https"
    response = RedirectResponse(url="/subscriptions/plans", status_code=302)
    response.delete_cookie("pending_user_id")
    response.set_cookie("access_token", access_token, httponly=True, samesite="lax", secure=is_https)
    response.set_cookie("refresh_token", refresh_token, httponly=True, samesite="lax", secure=is_https, max_age=60*60*24*7)
    return response


@router.post("/resend-otp")
async def resend_otp(request: Request, db: Session = Depends(get_db)):
    user_id = request.cookies.get("pending_user_id")
    if not user_id:
        return RedirectResponse(url="/auth/register", status_code=302)

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return RedirectResponse(url="/auth/register", status_code=302)

    otp = generate_otp()
    user.otp_code = hash_password(otp)
    user.otp_expires_at = datetime.utcnow() + timedelta(minutes=10)
    db.commit()

    send_otp_email(user.email, otp, user.full_name)
    return templates.TemplateResponse(
        "auth/verify_otp.html",
        {"request": request, "success": "New OTP sent to your email."},
    )


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("auth/login.html", {"request": request})


@router.post("/login")
@limiter.limit("5/minute")
async def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.email == email.lower().strip()).first()
    if not user or not verify_password(password, user.password_hash):
        return templates.TemplateResponse(
            "auth/login.html",
            {"request": request, "error": "Invalid email or password."},
            status_code=400,
        )

    if not user.is_verified:
        response = RedirectResponse(url="/auth/verify-otp", status_code=302)
        response.set_cookie("pending_user_id", str(user.id), max_age=600, httponly=True, samesite="lax")
        return response

    if user.is_suspended:
        return templates.TemplateResponse(
            "auth/login.html",
            {"request": request, "error": "Your account has been suspended. Contact support."},
            status_code=403,
        )

    access_token = create_access_token(str(user.id))
    refresh_token = create_refresh_token(str(user.id))

    is_https = request.url.scheme == "https"
    redirect_url = "/admin/dashboard" if user.role == "admin" else "/dashboard"
    response = RedirectResponse(url=redirect_url, status_code=302)
    response.set_cookie("access_token", access_token, httponly=True, samesite="lax", secure=is_https)
    response.set_cookie("refresh_token", refresh_token, httponly=True, samesite="lax", secure=is_https, max_age=60*60*24*7)
    return response


@router.post("/logout")
async def logout(request: Request):
    response = RedirectResponse(url="/auth/login", status_code=302)
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")
    return response
