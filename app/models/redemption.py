import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Enum, Integer, ForeignKey, Text, Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base


class RedemptionRequest(Base):
    __tablename__ = "redemption_requests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    points_requested = Column(Integer, nullable=False)
    amount_inr = Column(Numeric(10, 2), nullable=False)
    payment_method = Column(Enum("bank_transfer", "upi", name="payment_method_type"), nullable=False)
    bank_account_number = Column(String, nullable=True)
    bank_ifsc = Column(String, nullable=True)
    bank_account_name = Column(String, nullable=True)
    upi_id = Column(String, nullable=True)
    status = Column(
        Enum("pending", "processing", "completed", "rejected", name="redemption_status"),
        default="pending"
    )
    admin_note = Column(Text, nullable=True)
    processed_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    processed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="redemption_requests", foreign_keys=[user_id])
    processor = relationship("User", foreign_keys=[processed_by])
    points_ledger = relationship("PointsLedger", back_populates="redemption", foreign_keys="PointsLedger.redemption_id", lazy="dynamic")
