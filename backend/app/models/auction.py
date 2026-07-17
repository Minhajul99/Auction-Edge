import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional, List

from sqlalchemy import String, Numeric, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class Auction(Base):
    __tablename__ = "auctions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("items.id"), nullable=False)

    starting_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    reserve_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    current_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    status: Mapped[str] = mapped_column(String, nullable=False, default="Active")

    # Buy It Now — optional fixed price. If set and a bidder pays it,
    # the auction closes immediately (Closed - Sold), bypassing the timer.
    buy_it_now_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)

    # Payment stub — no real gateway integration, just tracks whether the
    # winner has clicked "Pay Now" on a closed/sold auction.
    payment_status: Mapped[str] = mapped_column(String, nullable=False, default="unpaid")
    # "unpaid" | "paid"

    # Relationships
    item: Mapped["Item"] = relationship("Item", back_populates="auctions")
    bids: Mapped[List["Bid"]] = relationship("Bid", back_populates="auction", order_by="Bid.timestamp")
    notifications: Mapped[List["Notification"]] = relationship("Notification", back_populates="auction")

    # NOTE: the actual logic for these lives in app/core/bidding.py,
    # kept separate from the model so it stays a pure, testable module
    # for mutation testing / TLA+ correspondence.
    # - checkReserveMet()
    # - extendSoftClose()
    # - closeAuction()
