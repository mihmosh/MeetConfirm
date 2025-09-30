"""SQLAlchemy database models."""
from datetime import datetime
from sqlalchemy import (
    Column,
    BigInteger,
    String,
    Text,
    DateTime,
    CheckConstraint,
    Index,
    ForeignKey,
    JSON,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()


class Event(Base):
    """Calendar event model."""
    
    __tablename__ = "events"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    calendar_event_id = Column(Text, nullable=False, unique=True, index=True)
    google_resource_id = Column(Text, nullable=True)
    organizer_email = Column(Text, nullable=False)
    attendee_email = Column(Text, nullable=False)
    start_time_utc = Column(DateTime(timezone=True), nullable=False, index=True)
    end_time_utc = Column(DateTime(timezone=True), nullable=False)
    timezone = Column(Text, nullable=False, default="Europe/Warsaw")
    status = Column(
        Text,
        nullable=False,
        default="pending",
    )
    confirm_token_hash = Column(Text, nullable=False)
    confirm_deadline_utc = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'confirmed', 'cancelled', 'completed')",
            name="check_status"
        ),
        Index("ix_events_status_start_time", "status", "start_time_utc"),
    )
    
    def __repr__(self):
        return f"<Event {self.calendar_event_id} - {self.status}>"


class Notification(Base):
    """Notification record model."""
    
    __tablename__ = "notifications"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    event_id = Column(
        BigInteger,
        ForeignKey("events.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    kind = Column(Text, nullable=False)
    channel = Column(Text, nullable=False, default="email")
    sent_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    meta = Column(JSON, nullable=False, default=dict)
    
    __table_args__ = (
        CheckConstraint(
            "kind IN ('confirm_request', 'cancel_notice')",
            name="check_kind"
        ),
        CheckConstraint(
            "channel IN ('email')",
            name="check_channel"
        ),
    )
    
    def __repr__(self):
        return f"<Notification {self.kind} for Event {self.event_id}>"


class AuditLog(Base):
    """Audit log model for tracking actions."""
    
    __tablename__ = "audit_logs"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    event_id = Column(
        BigInteger,
        ForeignKey("events.id", ondelete="CASCADE"),
        nullable=True,
        index=True
    )
    action = Column(Text, nullable=False)
    detail = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)
    
    def __repr__(self):
        return f"<AuditLog {self.action} at {self.created_at}>"
