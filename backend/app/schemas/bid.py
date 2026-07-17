import uuid
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, field_validator


class BidCreate(BaseModel):
    amount: Decimal

    @field_validator("amount")
    @classmethod
    def amount_positive(cls, v):
        if v <= 0:
            raise ValueError("bid amount must be a positive number")
        return v


class BidOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    auction_id: uuid.UUID
    amount: Decimal
    timestamp: datetime
    status: str
    # NOTE: bidder_id is intentionally excluded from the public view (UC4 masking).
    # Internal/owner-facing endpoints can use a separate schema that includes it.


class BidHistoryEntry(BaseModel):
    """Public bid history row — masked bidder identity per UC4."""
    amount: Decimal
    timestamp: datetime
    masked_bidder: str  # e.g. "Bidder #4", consistent per bidder per item
