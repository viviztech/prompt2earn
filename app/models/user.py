import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    full_name = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    is_verified = Column(Boolean, default=False)
    otp_code = Column(String, nullable=True)
    otp_expires_at = Column(DateTime, nullable=True)
    role = Column(Enum("user", "admin", name="user_role"), default="user", nullable=False)
    is_active = Column(Boolean, default=True)
    is_suspended = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    subscriptions = relationship("UserSubscription", back_populates="user", lazy="dynamic")
    submissions = relationship("Submission", back_populates="user", lazy="dynamic", foreign_keys="Submission.user_id")
    points_ledger = relationship("PointsLedger", back_populates="user", lazy="dynamic")
    redemption_requests = relationship("RedemptionRequest", back_populates="user", lazy="dynamic", foreign_keys="RedemptionRequest.user_id")
    payments = relationship("PaymentTransaction", back_populates="user", foreign_keys="PaymentTransaction.user_id", lazy="dynamic")
