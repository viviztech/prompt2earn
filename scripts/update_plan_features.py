"""
Update plan features to remove hardcoded 30% ROI claims.
Earnings are now based on actual submissions × point values.
Run: python scripts/update_plan_features.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.database import SessionLocal
from app.models.subscription import SubscriptionPlan

db = SessionLocal()

updates = {
    "basic": {
        "features": [
            "Poster & Caption prompts",
            "2 submissions/day",
            "Est. earn ₹198–₹264/month",
            "Referral bonus ₹100/invite",
            "Email support",
        ],
    },
    "pro": {
        "features": [
            "All 4 categories",
            "3 submissions/day",
            "Est. earn ₹356–₹475/month",
            "1.2× point multiplier",
            "Referral bonus ₹300/invite",
            "Priority review",
            "Email support",
        ],
    },
    "premium": {
        "features": [
            "All 4 categories",
            "5 submissions/day",
            "Est. earn ₹594–₹792/month",
            "1.5× point multiplier",
            "Referral bonus ₹600/invite",
            "Early access",
            "Priority review",
            "Dedicated support",
        ],
    },
    "agency": {
        "features": [
            "All 4 categories",
            "15 submissions/day",
            "Est. earn ₹1,782–₹2,376/month",
            "2× point multiplier",
            "Team of 3 users",
            "Referral bonus ₹1,500/invite",
            "Dedicated account manager",
            "Priority review",
            "Custom prompt requests",
        ],
    },
}

for plan_name, data in updates.items():
    plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.name == plan_name).first()
    if plan:
        plan.features = data["features"]
        print(f"✅ Updated {plan_name} features")
    else:
        print(f"⚠️  Plan '{plan_name}' not found")

db.commit()
db.close()
print("\n🎉 Plan features updated!")
