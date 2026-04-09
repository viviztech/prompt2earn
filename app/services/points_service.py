from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from app.models.points import PointsLedger
from app.models.submission import Submission
from app.models.subscription import UserSubscription
from app.config import get_settings
import uuid
import logging

settings = get_settings()
logger = logging.getLogger(__name__)


def get_active_subscription(user_id, db: Session):
    return db.query(UserSubscription).filter(
        UserSubscription.user_id == user_id,
        UserSubscription.status == "active",
        UserSubscription.expires_at > datetime.utcnow(),
    ).first()


def get_balance(user_id, db: Session) -> int:
    result = db.query(func.sum(PointsLedger.points)).filter(
        PointsLedger.user_id == user_id,
        or_(
            PointsLedger.transaction_type.in_(["redeemed", "expired", "adjusted"]),
            PointsLedger.expires_at > datetime.utcnow(),
        ),
    ).scalar()
    return max(0, result or 0)


def _add_ledger(user_id, points: int, transaction_type: str, description: str,
                db: Session, submission_id=None, redemption_id=None,
                expires_at=None) -> PointsLedger:
    current_balance = get_balance(user_id, db)
    entry = PointsLedger(
        user_id=user_id,
        submission_id=submission_id,
        redemption_id=redemption_id,
        transaction_type=transaction_type,
        points=points,
        balance_after=current_balance + points,
        description=description,
        expires_at=expires_at,
    )
    db.add(entry)
    return entry


def _default_expiry():
    return datetime.utcnow() + timedelta(days=settings.POINTS_EXPIRY_DAYS)


def _update_streak(user, db: Session):
    """Update current_streak and longest_streak based on last_active_date."""
    today = datetime.utcnow().date()
    last = user.last_active_date.date() if user.last_active_date else None

    if last is None or last < today:
        if last == today - timedelta(days=1):
            user.current_streak = (user.current_streak or 0) + 1
        elif last == today:
            pass  # already counted today
        else:
            user.current_streak = 1

        user.last_active_date = datetime.utcnow()
        if (user.current_streak or 0) > (user.longest_streak or 0):
            user.longest_streak = user.current_streak


def award_points(submission_id, db: Session) -> int:
    from app.services.settings_service import get_setting_int
    submission = db.query(Submission).filter(Submission.id == submission_id).first()
    if not submission:
        raise ValueError("Submission not found")

    sub = get_active_subscription(submission.user_id, db)
    multiplier = float(sub.plan.point_multiplier) if sub else 1.0
    points = int(submission.prompt.point_value * multiplier)

    expiry_days = get_setting_int("points_expiry_days", db) or settings.POINTS_EXPIRY_DAYS
    expires_at = datetime.utcnow() + timedelta(days=expiry_days)

    _add_ledger(
        user_id=submission.user_id,
        points=points,
        transaction_type="earned",
        description=f"Approved: {submission.prompt.title}",
        db=db,
        submission_id=submission.id,
        expires_at=expires_at,
    )
    submission.points_awarded = points
    submission.status = "approved"

    # Update streak
    from app.models.user import User
    user = db.query(User).filter(User.id == submission.user_id).first()
    if user:
        _update_streak(user, db)

        # Welcome bonus — one-time on first ever approval
        if not user.welcome_bonus_paid:
            welcome_pts = get_setting_int("welcome_bonus_points", db) or 10
            _add_ledger(
                user_id=user.id,
                points=welcome_pts,
                transaction_type="bonus",
                description=f"🎉 Welcome bonus — first submission approved!",
                db=db,
                expires_at=expires_at,
            )
            user.welcome_bonus_paid = True

        # Weekly streak bonus (every 7th consecutive day)
        streak = user.current_streak or 0
        if streak > 0 and streak % 7 == 0:
            streak_pts = get_setting_int("weekly_streak_bonus_points", db) or 20
            _add_ledger(
                user_id=user.id,
                points=streak_pts,
                transaction_type="bonus",
                description=f"🔥 {streak}-day streak bonus!",
                db=db,
                expires_at=expires_at,
            )

    db.commit()
    return points


def deduct_points(user_id, redemption_id, points: int, db: Session) -> bool:
    current_balance = get_balance(user_id, db)
    if current_balance < points:
        return False
    _add_ledger(
        user_id=user_id,
        redemption_id=redemption_id,
        points=-points,
        transaction_type="redeemed",
        description="Redemption request",
        db=db,
    )
    db.commit()
    return True


def restore_points(user_id, redemption_id, points: int, description: str, db: Session):
    _add_ledger(
        user_id=user_id,
        redemption_id=redemption_id,
        points=points,
        transaction_type="restored",
        description=description,
        db=db,
        expires_at=_default_expiry(),
    )
    db.commit()


def award_referral_bonus(referrer_id, referee_name: str, db: Session,
                         bonus_points: int = None) -> int:
    """Award bonus to referrer when their referee subscribes.
    Uses plan-specific bonus if provided, else falls back to config default."""
    bonus = bonus_points if bonus_points is not None else settings.REFERRAL_BONUS_POINTS
    _add_ledger(
        user_id=referrer_id,
        points=bonus,
        transaction_type="bonus",
        description=f"Referral bonus — {referee_name} subscribed",
        db=db,
        expires_at=_default_expiry(),
    )
    db.commit()
    return bonus


def award_daily_completion_bonus(user_id, bonus_points: int, db: Session) -> int:
    """Award bonus when user completes all available prompts for the day."""
    _add_ledger(
        user_id=user_id,
        points=bonus_points,
        transaction_type="bonus",
        description="🎯 Daily 100% completion bonus!",
        db=db,
        expires_at=_default_expiry(),
    )
    db.commit()
    return bonus_points


def get_leaderboard(db: Session, limit: int = 10) -> list:
    from app.models.user import User
    from sqlalchemy import desc
    results = (
        db.query(User.id, User.full_name, func.sum(PointsLedger.points).label("total_points"))
        .join(PointsLedger, User.id == PointsLedger.user_id)
        .filter(
            PointsLedger.transaction_type == "earned",
            PointsLedger.expires_at > datetime.utcnow(),
        )
        .group_by(User.id, User.full_name)
        .order_by(desc("total_points"))
        .limit(limit)
        .all()
    )
    return [{"rank": i+1, "name": r.full_name, "points": r.total_points or 0} for i, r in enumerate(results)]
