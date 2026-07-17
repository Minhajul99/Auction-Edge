import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.database import Base


class AuditLogEntry(Base):
    __tablename__ = "audit_log_entries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    action = Column(String, nullable=False)  # e.g. "bid_placed", "bid_retracted", "auction_closed"
    ip_address = Column(String, nullable=True)
    timestamp = Column(DateTime(timezone=True), nullable=False)

    # Generic reference instead of a hard FK to one table (Bid, Auction, etc.)
    # so this can log actions across any entity type.
    entity_type = Column(String, nullable=False)  # "Bid" | "Auction" | "Item" | "User"
    entity_id = Column(UUID(as_uuid=True), nullable=False)

    # Relationships
    user = relationship("User", back_populates="audit_logs")