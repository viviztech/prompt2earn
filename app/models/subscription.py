import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, Enum, Integer, Numeric, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.database import Base


class SubscriptionPlan(Base):
    __tablename__ = "subscription_plans"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(Enum("basic", "pro", "premium", name="plan_name"), unique=True, nullable=False)
    display_name = Column(String, nullable=False)
    price_inr = Column(Numeric(10, 2), nullable=False)
    duration_days = Column(Integer, nullable=False, default=30)
    point_multiplier = Column(Numeric(4, 2), nullable=False, default=1.0)
    allowed_categories = Column(JSONB, default=list)
    features = Column(JSONB, default=list)
    razorpay_plan_id = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Economics model
    max_daily_submissions = Column(Integer, nullable=False, default=2)
    referral_bonus_points = Column(Integer, nullable=False, default=24)  # pts awarded to referrer
    daily_completion_bonus = Column(Integer, nullable=False, default=5)  # pts for 100% day
    company_profit_pct = Column(Numeric(4, 2), nullable=False, default=20.0)  # always 20%

    subscriptions = relationship("UserSubscription", back_populates="plan", lazy="dynamic")


class UserSubscription(Base):
    __tablename__ = "user_subscriptions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    plan_id = Column(UUID(as_uuid=True), ForeignKey("subscription_plans.id"), nullable=False)
    status = Column(Enum("active", "expired", "cancelled", name="subscription_status"), default="active")
    razorpay_order_id = Column(String, nullable=True)
    razorpay_payment_id = Column(String, nullable=True)
    started_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="subscriptions")
    plan = relationship("SubscriptionPlan", back_populates="subscriptions")
    payments = relationship("PaymentTransaction", back_populates="subscription", lazy="dynamic")
