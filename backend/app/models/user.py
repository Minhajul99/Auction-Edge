import uuid
from sqlalchemy import Column, String, Boolean, ARRAY, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    email_verified = Column(Boolean, default=False, nullable=False)
    roles = Column(ARRAY(String), default=list)  # e.g. ["seller", "bidder"]
    is_admin = Column(Boolean, default=False, nullable=False)
    avatar = Column(String, nullable=True)  # base64 data URL, same storage pattern as Item.photos

    # Password reset -- single-use token + expiry, cleared once consumed.
    reset_token = Column(String, nullable=True, unique=True)
    reset_token_expires_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    items = relationship("Item", back_populates="seller")
    bids = relationship("Bid", back_populates="bidder")
    notifications = relationship("Notification", back_populates="user")
    audit_logs = relationship("AuditLogEntry", back_populates="user")
    wallet = relationship("Wallet", back_populates="user", uselist=False)
