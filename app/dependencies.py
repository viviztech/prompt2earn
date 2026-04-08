from fastapi import Request, HTTPException, Depends, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from jose import JWTError, jwt
from app.database import get_db
from app.config import get_settings

settings = get_settings()


def get_current_user(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("access_token")
    if not token:
        raise RedirectException(url="/auth/login")
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise RedirectException(url="/auth/login")
    except JWTError:
        raise RedirectException(url="/auth/login")

    from app.models.user import User
    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    if user is None or user.is_suspended:
        raise RedirectException(url="/auth/login")
    return user


def get_current_user_optional(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("access_token")
    if not token:
        return None
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            return None
    except JWTError:
        return None

    from app.models.user import User
    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    if user is None or user.is_suspended:
        return None
    return user


def require_admin(request: Request, db: Session = Depends(get_db)):
    current_user = get_current_user(request, db)
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return current_user


def require_active_subscription(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    from app.models.subscription import UserSubscription
    from datetime import datetime
    sub = db.query(UserSubscription).filter(
        UserSubscription.user_id == current_user.id,
        UserSubscription.status == "active",
        UserSubscription.expires_at > datetime.utcnow()
    ).first()
    if not sub:
        raise RedirectException(url="/subscriptions/plans")
    return current_user


class RedirectException(Exception):
    def __init__(self, url: str, status_code: int = 302):
        self.url = url
        self.status_code = status_code
