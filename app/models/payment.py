import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Enum, ForeignKey, Numeric, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base


class PaymentTransaction(Base):
    __tablename__ = "payment_transactions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    subscription_id = Column(UUID(as_uuid=True), ForeignKey("user_subscriptions.id"), nullable=True)
    plan_id = Column(UUID(as_uuid=True), ForeignKey("subscription_plans.id"), nullable=True)

    # Payment method: razorpay or manual
    payment_method = Column(Enum("razorpay", "manual", name="txn_payment_method"), default="razorpay", nullable=False)

    # Razorpay fields
    razorpay_order_id = Column(String, unique=True, nullable=True)
    razorpay_payment_id = Column(String, nullable=True)
    razorpay_signature = Column(String, nullable=True)

    # Manual payment fields
    manual_transaction_id = Column(String, nullable=True)
    manual_screenshot_url = Column(String, nullable=True)  # S3 key
    admin_note = Column(Text, nullable=True)
    reviewed_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)

    amount_inr = Column(Numeric(10, 2), nullable=False)
    status = Column(
        Enum("created", "paid", "failed", "refunded", "pending_verification", "rejected", name="payment_status"),
        default="created"
    )
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="payments", foreign_keys=[user_id])
    reviewer = relationship("User", foreign_keys=[reviewed_by])
    subscription = relationship("UserSubscription", back_populates="payments")
