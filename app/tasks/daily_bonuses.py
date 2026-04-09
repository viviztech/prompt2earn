"""
Daily bonus jobs — runs at midnight UTC.
1. Daily 100% completion bonus: users who submitted all available prompts yesterday
2. Monthly streak bonus: users who have been active 25+ days this month
"""
from datetime import datetime, timedelta
import logging
from app.database import SessionLocal
from app.services.points_service import award_daily_completion_bonus, get_balance

logger = logging.getLogger(__name__)


def daily_completion_bonus_job():
    """
    Award completion bonus to users who submitted to ALL active prompts yesterday.
    Runs at 00:05 UTC so yesterday's data is complete.
    """
    db = SessionLocal()
    try:
        from app.models.submission import Submission
        from app.models.subscription import UserSubscription, SubscriptionPlan
        from app.models.prompt import Prompt
        from app.models.user import User
        from app.models.points import PointsLedger

        yesterday_start = (datetime.utcnow() - timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0)
        yesterday_end = yesterday_start + timedelta(days=1)

        # Prompts that were active and had deadline within yesterday
        active_prompts_yesterday = db.query(Prompt).filter(
            Prompt.is_active == True,
            Prompt.deadline >= yesterday_start,
            Prompt.deadline < yesterday_end + timedelta(days=1),  # some grace
        ).all()

        if not active_prompts_yesterday:
            logger.info("Daily completion bonus: no prompts active yesterday")
            return

        prompt_ids = [p.id for p in active_prompts_yesterday]
        total_prompts = len(prompt_ids)

        # Find users who submitted to all of them yesterday
        users_with_active_sub = (
            db.query(UserSubscription)
            .filter(
                UserSubscription.status == "active",
                UserSubscription.expires_at > datetime.utcnow(),
            )
            .all()
        )

        awarded = 0
        for sub in users_with_active_sub:
            # Count how many of yesterday's prompts this user submitted
            submitted_count = db.query(Submission).filter(
                Submission.user_id == sub.user_id,
                Submission.prompt_id.in_(prompt_ids),
                Submission.submitted_at >= yesterday_start,
                Submission.submitted_at < yesterday_end,
                Submission.status.in_(["pending", "approved"]),
            ).count()

            # Check per-plan submission cap
            max_daily = getattr(sub.plan, "max_daily_submissions", 2) or 2
            accessible_prompts = [
                p for p in active_prompts_yesterday
                if not p.visible_to or sub.plan.name in p.visible_to
            ]
            prompts_to_complete = min(len(accessible_prompts), max_daily)

            if prompts_to_complete > 0 and submitted_count >= prompts_to_complete:
                # Check not already awarded today
                already = db.query(PointsLedger).filter(
                    PointsLedger.user_id == sub.user_id,
                    PointsLedger.transaction_type == "bonus",
                    PointsLedger.description.like("🎯 Daily 100%%"),
                    PointsLedger.created_at >= yesterday_start,
                    PointsLedger.created_at < yesterday_end + timedelta(days=1),
                ).first()
                if not already:
                    bonus = getattr(sub.plan, "daily_completion_bonus", 5)
                    award_daily_completion_bonus(sub.user_id, bonus, db)
                    awarded += 1

        logger.info(f"Daily completion bonus: awarded to {awarded} users")
    except Exception as e:
        logger.error(f"Daily completion bonus job failed: {e}")
        db.rollback()
    finally:
        db.close()


def monthly_streak_bonus_job():
    """
    Award monthly streak bonus to users active 25+ days in the current month.
    Runs on the 1st of each month at 00:10 UTC.
    """
    db = SessionLocal()
    try:
        from app.models.submission import Submission
        from app.models.subscription import UserSubscription
        from app.models.points import PointsLedger
        from sqlalchemy import func

        # Last month window
        now = datetime.utcnow()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)
        month_start = month_start.replace(day=1)
        month_end = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        # Users with active subscriptions
        active_subs = db.query(UserSubscription).filter(
            UserSubscription.status == "active",
        ).all()

        from app.services.settings_service import get_setting_int
        threshold = get_setting_int("monthly_streak_threshold", db) or 25
        monthly_bonus = get_setting_int("monthly_streak_bonus_points", db) or 50

        awarded = 0
        for sub in active_subs:
            # Count distinct active days last month
            active_days = db.query(
                func.count(func.distinct(func.date(Submission.submitted_at)))
            ).filter(
                Submission.user_id == sub.user_id,
                Submission.submitted_at >= month_start,
                Submission.submitted_at < month_end,
                Submission.status.in_(["pending", "approved"]),
            ).scalar() or 0

            if active_days >= threshold:
                # Check not already awarded
                already = db.query(PointsLedger).filter(
                    PointsLedger.user_id == sub.user_id,
                    PointsLedger.transaction_type == "bonus",
                    PointsLedger.description.like("📅 Monthly streak%%"),
                    PointsLedger.created_at >= month_end - timedelta(days=5),
                ).first()
                if not already:
                    award_daily_completion_bonus(sub.user_id, monthly_bonus, db)
                    # Rewrite description for monthly
                    from app.models.points import PointsLedger as PL
                    last = db.query(PL).filter(
                        PL.user_id == sub.user_id,
                        PL.description.like("🎯 Daily%%"),
                    ).order_by(PL.created_at.desc()).first()
                    if last:
                        last.description = f"📅 Monthly streak bonus — {active_days} active days!"
                        db.commit()
                    awarded += 1

        logger.info(f"Monthly streak bonus: awarded to {awarded} users")
    except Exception as e:
        logger.error(f"Monthly streak bonus job failed: {e}")
        db.rollback()
    finally:
        db.close()
