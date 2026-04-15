"""
Fix all existing prompt point values to max 5 pts to match 30% ROI promise.
Run: python scripts/fix_prompt_points.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.database import SessionLocal
from app.models.prompt import Prompt

db = SessionLocal()

prompts = db.query(Prompt).all()
updated = 0
for p in prompts:
    if p.point_value > 5:
        p.point_value = 5
        updated += 1

db.commit()
db.close()
print(f"✅ Fixed {updated} prompts to max 5 pts. Total prompts: {len(prompts)}")
