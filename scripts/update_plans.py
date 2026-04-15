"""
Update subscription plan pricing and earnings to new structure.
Run: python scripts/update_plans.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.database import SessionLocal
from app.models.subscription import SubscriptionPlan

db = SessionLocal()

updates = {
    "basic": {
        "price_inr": 999,
        "point_multiplier": 1.0,
        "max_daily_submissions": 2,
        "referral_bonus_points": 100,
        "daily_completion_bonus": 10,
        "company_profit_pct": 70.0,
        "features": ["Poster & Caption prompts", "2 submissions/day", "Earn up to ₹300/month", "Referral bonus ₹100/invite", "Email support"],
    },
    "pro": {
        "price_inr": 2999,
        "point_multiplier": 1.2,
        "max_daily_submissions": 3,
        "referral_bonus_points": 300,
        "daily_completion_bonus": 20,
        "company_profit_pct": 70.0,
        "features": ["All 4 categories", "3 submissions/day", "Earn up to ₹900/month", "1.2× point multiplier", "Referral bonus ₹300/invite", "Priority review", "Email support"],
    },
    "premium": {
        "price_inr": 5999,
        "point_multiplier": 1.5,
        "max_daily_submissions": 5,
        "referral_bonus_points": 600,
        "daily_completion_bonus": 40,
        "company_profit_pct": 70.0,
        "features": ["All 4 categories", "5 submissions/day", "Earn up to ₹1,800/month", "1.5× point multiplier", "Referral bonus ₹600/invite", "Early access", "Priority review", "Dedicated support"],
    },
}

for plan_name, data in updates.items():
    plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.name == plan_name).first()
    if plan:
        for key, val in data.items():
            setattr(plan, key, val)
        print(f"✅ Updated {plan_name}: ₹{data['price_inr']}")
    else:
        print(f"⚠️  Plan '{plan_name}' not found")

db.commit()
db.close()
print("\n🎉 Plans updated successfully!")
