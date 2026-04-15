"""
Migration: Add free/agency plans, quality_score column, is_free/wallet_locked plan flags.
Run: python scripts/migrate_new_plans.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.database import SessionLocal, engine
from sqlalchemy import text

db = SessionLocal()

print("Running migrations...")

# 1. Add quality_score to submissions
try:
    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE submissions ADD COLUMN IF NOT EXISTS quality_score INTEGER"))
        conn.commit()
    print("✅ Added quality_score to submissions")
except Exception as e:
    print(f"⚠️  quality_score: {e}")

# 2. Add is_free and wallet_locked to subscription_plans
try:
    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE subscription_plans ADD COLUMN IF NOT EXISTS is_free BOOLEAN DEFAULT FALSE"))
        conn.execute(text("ALTER TABLE subscription_plans ADD COLUMN IF NOT EXISTS wallet_locked BOOLEAN DEFAULT FALSE"))
        conn.commit()
    print("✅ Added is_free, wallet_locked to subscription_plans")
except Exception as e:
    print(f"⚠️  plan flags: {e}")

# 3. Alter plan_name enum to add free and agency
try:
    with engine.connect() as conn:
        conn.execute(text("ALTER TYPE plan_name ADD VALUE IF NOT EXISTS 'free'"))
        conn.execute(text("ALTER TYPE plan_name ADD VALUE IF NOT EXISTS 'agency'"))
        conn.commit()
    print("✅ Extended plan_name enum with free, agency")
except Exception as e:
    print(f"⚠️  enum extend: {e}")

# 4. Insert free plan
try:
    from app.models.subscription import SubscriptionPlan
    if not db.query(SubscriptionPlan).filter(SubscriptionPlan.name == "free").first():
        free_plan = SubscriptionPlan(
            name="free", display_name="Free", price_inr=0,
            duration_days=30, point_multiplier=1.0,
            max_daily_submissions=1,
            referral_bonus_points=0,
            daily_completion_bonus=0,
            company_profit_pct=100.0,
            allowed_categories=["poster"],
            is_free=True,
            wallet_locked=True,
            features=["1 poster submission/day", "Earnings locked until you subscribe", "Unlock wallet by upgrading to any paid plan"],
            is_active=True,
        )
        db.add(free_plan)
        db.commit()
        print("✅ Free plan created")
    else:
        print("ℹ️  Free plan already exists")
except Exception as e:
    db.rollback()
    print(f"⚠️  Free plan: {e}")

# 5. Insert agency plan
try:
    from app.models.subscription import SubscriptionPlan
    if not db.query(SubscriptionPlan).filter(SubscriptionPlan.name == "agency").first():
        agency_plan = SubscriptionPlan(
            name="agency", display_name="Agency", price_inr=14999,
            duration_days=30, point_multiplier=2.0,
            max_daily_submissions=15,
            referral_bonus_points=1500,
            daily_completion_bonus=100,
            company_profit_pct=70.0,
            allowed_categories=["poster", "caption", "video", "audio"],
            is_free=False,
            wallet_locked=False,
            features=["All 4 categories", "15 submissions/day", "Earn up to ₹4,500/month", "2× point multiplier", "Team of 3 users", "Referral bonus ₹1,500/invite", "Dedicated account manager", "Priority review", "Custom prompt requests"],
            is_active=True,
        )
        db.add(agency_plan)
        db.commit()
        print("✅ Agency plan created")
    else:
        print("ℹ️  Agency plan already exists")
except Exception as e:
    db.rollback()
    print(f"⚠️  Agency plan: {e}")

# 6. Add sponsor fields to prompts
try:
    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE prompts ADD COLUMN IF NOT EXISTS is_sponsored BOOLEAN DEFAULT FALSE"))
        conn.execute(text("ALTER TABLE prompts ADD COLUMN IF NOT EXISTS sponsor_name VARCHAR"))
        conn.execute(text("ALTER TABLE prompts ADD COLUMN IF NOT EXISTS sponsor_budget_inr INTEGER"))
        conn.commit()
    print("✅ Added sponsorship columns to prompts")
except Exception as e:
    print(f"⚠️  sponsor columns: {e}")

db.close()
print("\n🎉 Migration complete!")
