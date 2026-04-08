import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, Enum, Integer, Text, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base


class Submission(Base):
    __tablename__ = "submissions"
    __table_args__ = (UniqueConstraint("user_id", "prompt_id", name="uq_user_prompt"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    prompt_id = Column(UUID(as_uuid=True), ForeignKey("prompts.id"), nullable=False, index=True)
    file_url = Column(String, nullable=False)
    file_type = Column(String, nullable=False)
    file_size_bytes = Column(Integer, nullable=True)
    original_filename = Column(String, nullable=True)
    status = Column(Enum("pending", "approved", "rejected", name="submission_status"), default="pending")
    review_note = Column(Text, nullable=True)
    reviewed_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    points_awarded = Column(Integer, default=0)
    submitted_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="submissions", foreign_keys=[user_id])
    reviewer = relationship("User", foreign_keys=[reviewed_by])
    prompt = relationship("Prompt", back_populates="submissions")
    points_ledger = relationship("PointsLedger", back_populates="submission", uselist=False)
