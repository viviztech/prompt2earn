from datetime import datetime
import logging
from app.database import SessionLocal
from app.models.points import PointsLedger
from app.services.points_service import get_balance

logger = logging.getLogger(__name__)


def expire_points_job():
    db = SessionLocal()
    try:
        now = datetime.utcnow()
        expired_entries = db.query(PointsLedger).filter(
            PointsLedger.transaction_type == "earned",
            PointsLedger.expires_at <= now,
            PointsLedger.points > 0,
        ).all()

        count = 0
        for entry in expired_entries:
            # Check if already expired (no duplicate expiry entry)
            already_expired = db.query(PointsLedger).filter(
                PointsLedger.submission_id == entry.submission_id,
                PointsLedger.transaction_type == "expired",
            ).first()
            if already_expired:
                continue

            current_balance = get_balance(entry.user_id, db)
            if current_balance <= 0:
                continue

            debit = min(entry.points, current_balance)
            expiry_ledger = PointsLedger(
                user_id=entry.user_id,
                submission_id=entry.submission_id,
                transaction_type="expired",
                points=-debit,
                balance_after=current_balance - debit,
                description=f"Points expired (earned on {entry.created_at.strftime('%Y-%m-%d')})",
            )
            db.add(expiry_ledger)
            count += 1

        db.commit()
        logger.info(f"Points expiry job: processed {count} expired entries")
    except Exception as e:
        logger.error(f"Points expiry job failed: {e}")
        db.rollback()
    finally:
        db.close()
