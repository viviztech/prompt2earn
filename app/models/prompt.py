import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, Enum, Integer, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.database import Base


class PromptCategory(Base):
    __tablename__ = "prompt_categories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(Enum("poster", "video", "audio", "caption", name="category_name"), unique=True, nullable=False)
    display_name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    allowed_file_types = Column(JSONB, default=list)
    max_file_size_mb = Column(Integer, default=10)
    is_active = Column(Boolean, default=True)

    prompts = relationship("Prompt", back_populates="category", lazy="dynamic")


class Prompt(Base):
    __tablename__ = "prompts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    category_id = Column(UUID(as_uuid=True), ForeignKey("prompt_categories.id"), nullable=False)
    point_value = Column(Integer, nullable=False)
    deadline = Column(DateTime, nullable=False)
    visible_to = Column(JSONB, default=lambda: ["basic", "pro", "premium"])
    is_active = Column(Boolean, default=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Prompt locking — once claimed by a user, hidden from all others
    assigned_to = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    assigned_at = Column(DateTime, nullable=True)

    category = relationship("PromptCategory", back_populates="prompts")
    creator = relationship("User", foreign_keys=[created_by])
    assignee = relationship("User", foreign_keys=[assigned_to])
    submissions = relationship("Submission", back_populates="prompt", lazy="dynamic")
