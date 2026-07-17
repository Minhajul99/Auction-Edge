"""
Equivalence partitioning tests (plan section 3.3), complementing BVA.

Category and duration_days are both rejected at the Pydantic layer before
any endpoint code runs -- these tests confirm the valid/invalid partitions
are drawn where the plan says they are, without needing a DB or HTTP call.
"""

import uuid
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas.item import ItemCreate, ALLOWED_CATEGORIES
from app.schemas.auction import AuctionCreate


@pytest.mark.parametrize("category", sorted(ALLOWED_CATEGORIES))
def test_item_create_accepts_every_valid_category(category):
    item = ItemCreate(title="T", category=category, photos=["url"])
    assert item.category == category


@pytest.mark.parametrize("category", ["Vehicles", "gaming", "", "Electronics", "Gaming "])
def test_item_create_rejects_invalid_category(category):
    with pytest.raises(ValidationError):
        ItemCreate(title="T", category=category, photos=["url"])


@pytest.mark.parametrize("duration", [3, 5, 7, 10])
def test_auction_create_accepts_valid_duration_presets(duration):
    auction = AuctionCreate(item_id=uuid.uuid4(), starting_price=Decimal("10"), duration_days=duration)
    assert auction.duration_days == duration


@pytest.mark.parametrize("duration", [1, 4, 14, 0, -3])
def test_auction_create_rejects_arbitrary_duration_values(duration):
    with pytest.raises(ValidationError):
        AuctionCreate(item_id=uuid.uuid4(), starting_price=Decimal("10"), duration_days=duration)
