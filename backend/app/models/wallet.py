import uuid
from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class Wallet(Base):
    __tablename__ = "wallets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), unique=True, nullable=False
    )

    # Total funds. No real payment gateway — this is seeded with a demo
    # starting balance on registration, purely for testing bid-hold logic.
    balance: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=Decimal("1000.00"))

    # Sum of all currently-active holds across every auction this user has
    # an active bid on. available = balance - held_amount.
    held_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=Decimal("0.00"))

    user = relationship("User", back_populates="wallet")
