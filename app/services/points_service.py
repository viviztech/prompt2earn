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


def award_points(submission_id, db: Session) -> int:
    submission = db.query(Submission).filter(Submission.id == submission_id).first()
    if not submission:
        raise ValueError("Submission not found")

    sub = get_active_subscription(submission.user_id, db)
    multiplier = float(sub.plan.point_multiplier) if sub else 1.0
    points = int(submission.prompt.point_value * multiplier)

    current_balance = get_balance(submission.user_id, db)
    expires_at = datetime.utcnow() + timedelta(days=settings.POINTS_EXPIRY_DAYS)

    ledger = PointsLedger(
        user_id=submission.user_id,
        submission_id=submission.id,
        transaction_type="earned",
        points=points,
        balance_after=current_balance + points,
        description=f"Approved: {submission.prompt.title}",
        expires_at=expires_at,
    )
    submission.points_awarded = points
    submission.status = "approved"
    db.add(ledger)
    db.commit()
    return points


def deduct_points(user_id, redemption_id, points: int, db: Session) -> bool:
    current_balance = get_balance(user_id, db)
    if current_balance < points:
        return False

    ledger = PointsLedger(
        user_id=user_id,
        redemption_id=redemption_id,
        transaction_type="redeemed",
        points=-points,
        balance_after=current_balance - points,
        description=f"Redemption request",
    )
    db.add(ledger)
    db.commit()
    return True


def restore_points(user_id, redemption_id, points: int, description: str, db: Session):
    current_balance = get_balance(user_id, db)
    ledger = PointsLedger(
        user_id=user_id,
        redemption_id=redemption_id,
        transaction_type="restored",
        points=points,
        balance_after=current_balance + points,
        description=description,
    )
    db.add(ledger)
    db.commit()


def award_referral_bonus(referrer_id, referee_name: str, db: Session) -> int:
    """Award bonus points to the referrer when their referee subscribes for the first time."""
    bonus = settings.REFERRAL_BONUS_POINTS
    current_balance = get_balance(referrer_id, db)
    from datetime import timedelta
    expires_at = datetime.utcnow() + timedelta(days=settings.POINTS_EXPIRY_DAYS)
    ledger = PointsLedger(
        user_id=referrer_id,
        transaction_type="bonus",
        points=bonus,
        balance_after=current_balance + bonus,
        description=f"Referral bonus — {referee_name} subscribed",
        expires_at=expires_at,
    )
    db.add(ledger)
    db.commit()
    return bonus


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
