import uuid
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.database import Base


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    auction_id = Column(UUID(as_uuid=True), ForeignKey("auctions.id"), nullable=True)

    type = Column(String, nullable=False)  # e.g. "outbid", "won", "reserve_met", "auction_closed"
    read = Column(Boolean, default=False, nullable=False)
    sent_at = Column(DateTime(timezone=True), nullable=False)

    # Relationships
    user = relationship("User", back_populates="notifications")
    auction = relationship("Auction", back_populates="notifications")