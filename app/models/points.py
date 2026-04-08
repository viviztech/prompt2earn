import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Enum, Integer, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base


class PointsLedger(Base):
    __tablename__ = "points_ledger"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    submission_id = Column(UUID(as_uuid=True), ForeignKey("submissions.id"), nullable=True)
    redemption_id = Column(UUID(as_uuid=True), ForeignKey("redemption_requests.id"), nullable=True)
    transaction_type = Column(
        Enum("earned", "redeemed", "expired", "bonus", "adjusted", "restored", name="transaction_type"),
        nullable=False
    )
    points = Column(Integer, nullable=False)
    balance_after = Column(Integer, nullable=False)
    description = Column(Text, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="points_ledger")
    submission = relationship("Submission", back_populates="points_ledger")
    redemption = relationship("RedemptionRequest", back_populates="points_ledger", foreign_keys=[redemption_id])
