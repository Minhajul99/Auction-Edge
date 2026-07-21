import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional, Literal
from pydantic import BaseModel, ConfigDict, field_validator

DurationDays = Literal[1, 3, 5, 7, 10, 14]


class AuctionCreate(BaseModel):
    item_id: uuid.UUID
    starting_price: Decimal
    reserve_price: Optional[Decimal] = None
    buy_it_now_price: Optional[Decimal] = None
    duration_days: DurationDays

    @field_validator("starting_price")
    @classmethod
    def starting_price_positive(cls, v):
        if v <= 0:
            raise ValueError("starting_price must be a positive number")
        return v

    @field_validator("reserve_price")
    @classmethod
    def reserve_price_above_starting(cls, v, info):
        starting = info.data.get("starting_price")
        if v is not None and starting is not None and v <= starting:
            raise ValueError("reserve_price must be higher than starting_price")
        return v

    @field_validator("buy_it_now_price")
    @classmethod
    def buy_it_now_above_starting_and_reserve(cls, v, info):
        if v is None:
            return v
        starting = info.data.get("starting_price")
        reserve = info.data.get("reserve_price")
        if starting is not None and v <= starting:
            raise ValueError("buy_it_now_price must be higher than starting_price")
        if reserve is not None and v <= reserve:
            raise ValueError("buy_it_now_price must be higher than reserve_price")
        return v


class AuctionOut(BaseModel):
    """Public-facing auction view. Deliberately omits reserve_price."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    item_id: uuid.UUID
    seller_id: uuid.UUID
    title: str
    description: Optional[str] = None
    starting_price: Decimal
    current_price: Decimal
    start_time: datetime
    end_time: datetime
    status: str
    reserve_met: bool = False  # derived flag, not the raw reserve_price
    payment_status: str = "unpaid"
    photo: Optional[str] = None  # first photo from the associated Item, for display
    buy_it_now_price: Optional[Decimal] = None
