#!/usr/bin/env python3
"""Seed the database with initial data."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal, engine
from app.models import *
from app.services.auth_service import hash_password
from datetime import datetime, timedelta

def seed():
    db = SessionLocal()
    try:
        # Subscription Plans
        if not db.query(SubscriptionPlan).first():
            plans = [
                SubscriptionPlan(
                    name="basic", display_name="Basic", price_inr=199,
                    duration_days=30, point_multiplier=1.0,
                    allowed_categories=["poster", "caption"],
                    features=["Access to Poster prompts", "Access to Caption prompts", "Up to 30 prompts/month", "Email support"],
                    is_active=True,
                ),
                SubscriptionPlan(
                    name="pro", display_name="Pro", price_inr=399,
                    duration_days=30, point_multiplier=1.0,
                    allowed_categories=["poster", "caption", "video", "audio"],
                    features=["All categories", "Up to 60 prompts/month", "Priority review", "Email support"],
                    is_active=True,
                ),
                SubscriptionPlan(
                    name="premium", display_name="Premium", price_inr=699,
                    duration_days=30, point_multiplier=1.5,
                    allowed_categories=["poster", "caption", "video", "audio"],
                    features=["All categories", "Unlimited prompts", "1.5× point multiplier", "Early access to prompts", "Priority review", "Dedicated support"],
                    is_active=True,
                ),
            ]
            db.add_all(plans)
            db.flush()
            print("✅ Subscription plans created")

        # Prompt Categories
        if not db.query(PromptCategory).first():
            categories = [
                PromptCategory(name="poster", display_name="Social Media Poster",
                    description="Create eye-catching posters for social media",
                    allowed_file_types=["jpg", "jpeg", "png", "webp"], max_file_size_mb=10),
                PromptCategory(name="video", display_name="Video / Reel",
                    description="Short-form video content for social platforms",
                    allowed_file_types=["mp4", "mov", "webm"], max_file_size_mb=500),
                PromptCategory(name="audio", display_name="Audio / Voiceover",
                    description="AI-generated audio, narrations, voiceovers",
                    allowed_file_types=["mp3", "wav", "ogg"], max_file_size_mb=50),
                PromptCategory(name="caption", display_name="Blog & Caption",
                    description="Written content, captions, and blog posts",
                    allowed_file_types=["txt", "pdf"], max_file_size_mb=2),
            ]
            db.add_all(categories)
            db.flush()
            print("✅ Prompt categories created")

        # Admin User
        from app.models.user import User
        admin = db.query(User).filter(User.email == "admin@promptearn.com").first()
        if not admin:
            admin = User(
                email="admin@promptearn.com",
                password_hash=hash_password("Admin@1234"),
                full_name="PromptEarn Admin",
                role="admin",
                is_verified=True,
                is_active=True,
            )
            db.add(admin)
            db.flush()
            print("✅ Admin user created: admin@promptearn.com / Admin@1234")

        # Sample prompts
        from app.models.prompt import Prompt, PromptCategory
        if not db.query(Prompt).first():
            poster_cat = db.query(PromptCategory).filter(PromptCategory.name == "poster").first()
            caption_cat = db.query(PromptCategory).filter(PromptCategory.name == "caption").first()
            now = datetime.utcnow()

            sample_prompts = [
                Prompt(title="Diwali Celebration Poster",
                    description="Create a vibrant Diwali celebration poster for Instagram (1080×1080px). Include diyas, rangoli patterns, and festive text 'Happy Diwali'. Use warm golden and orange tones. Add a brand logo placeholder at the bottom.",
                    category_id=poster_cat.id, point_value=50,
                    deadline=now + timedelta(days=1), visible_to=["basic", "pro", "premium"],
                    created_by=admin.id, is_active=True),
                Prompt(title="Morning Motivation Instagram Caption",
                    description="Write 5 unique Instagram captions for a morning motivation post. Each caption should be 100-150 words, include 10 relevant hashtags, and end with a call-to-action. Tone: Energetic and positive. Target audience: Young professionals.",
                    category_id=caption_cat.id, point_value=30,
                    deadline=now + timedelta(days=1), visible_to=["basic", "pro", "premium"],
                    created_by=admin.id, is_active=True),
            ]
            db.add_all(sample_prompts)
            print("✅ Sample prompts created")

        db.commit()
        print("\n🎉 Database seeded successfully!")
        print("\nAdmin login: admin@promptearn.com / Admin@1234")

    except Exception as e:
        print(f"❌ Seeding failed: {e}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    seed()
