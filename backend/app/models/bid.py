import uuid
from sqlalchemy import Column, String, Numeric, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.database import Base


class Bid(Base):
    __tablename__ = "bids"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    auction_id = Column(UUID(as_uuid=True), ForeignKey("auctions.id"), nullable=False)
    bidder_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    amount = Column(Numeric(10, 2), nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False)  # millisecond precision

    status = Column(String, nullable=False, default="active")
    # active | withdrawn | outbid

    # Relationships
    auction = relationship("Auction", back_populates="bids")
    bidder = relationship("User", back_populates="bids")

    # NOTE: isRetractable() logic (15-min window, one retraction per bid)
    # lives in app/core/bidding.py, not here — keeps this a plain data model.