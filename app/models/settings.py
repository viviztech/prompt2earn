import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base


class PlatformSettings(Base):
    """Key-value store for admin-editable platform configuration."""
    __tablename__ = "platform_settings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    key = Column(String(64), unique=True, nullable=False, index=True)
    value = Column(Text, nullable=False)
    label = Column(String(128), nullable=False)           # human-readable label
    description = Column(Text, nullable=True)             # shown as help text in admin
    group = Column(String(64), nullable=False, default="general")  # for grouping in UI
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
