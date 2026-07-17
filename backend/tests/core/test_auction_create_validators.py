"""
Use Case Testing derived from UC2 (Create Auction Listing): AuctionCreate's
three field validators in schemas/auction.py had zero test coverage before
this file -- starting_price must be positive, reserve_price must exceed
starting_price, and buy_it_now_price must exceed both.
"""

import uuid
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas.auction import AuctionCreate


def _kwargs(**overrides):
    kwargs = dict(item_id=uuid.uuid4(), starting_price=Decimal("50"), duration_days=7)
    kwargs.update(overrides)
    return kwargs


# --- starting_price must be positive ---

def test_auction_create_accepts_positive_starting_price():
    auction = AuctionCreate(**_kwargs(starting_price=Decimal("50")))
    assert auction.starting_price == Decimal("50")


@pytest.mark.parametrize("starting_price", [Decimal("0"), Decimal("-1"), Decimal("-0.01")])
def test_auction_create_rejects_non_positive_starting_price(starting_price):
    with pytest.raises(ValidationError):
        AuctionCreate(**_kwargs(starting_price=starting_price))


# --- reserve_price must exceed starting_price (when set) ---

def test_auction_create_reserve_price_is_optional():
    auction = AuctionCreate(**_kwargs(reserve_price=None))
    assert auction.reserve_price is None


def test_auction_create_accepts_reserve_price_above_starting():
    auction = AuctionCreate(**_kwargs(starting_price=Decimal("50"), reserve_price=Decimal("100")))
    assert auction.reserve_price == Decimal("100")


@pytest.mark.parametrize("reserve_price", [Decimal("50"), Decimal("49.99")])
def test_auction_create_rejects_reserve_price_at_or_below_starting(reserve_price):
    with pytest.raises(ValidationError):
        AuctionCreate(**_kwargs(starting_price=Decimal("50"), reserve_price=reserve_price))


# --- buy_it_now_price must exceed both starting_price and reserve_price ---

def test_auction_create_buy_it_now_price_is_optional():
    auction = AuctionCreate(**_kwargs(buy_it_now_price=None))
    assert auction.buy_it_now_price is None


def test_auction_create_accepts_buy_it_now_above_starting_with_no_reserve():
    auction = AuctionCreate(**_kwargs(starting_price=Decimal("50"), buy_it_now_price=Decimal("200")))
    assert auction.buy_it_now_price == Decimal("200")


@pytest.mark.parametrize("buy_it_now_price", [Decimal("50"), Decimal("49.99")])
def test_auction_create_rejects_buy_it_now_at_or_below_starting(buy_it_now_price):
    with pytest.raises(ValidationError):
        AuctionCreate(**_kwargs(starting_price=Decimal("50"), buy_it_now_price=buy_it_now_price))


def test_auction_create_accepts_buy_it_now_above_both_starting_and_reserve():
    auction = AuctionCreate(
        **_kwargs(starting_price=Decimal("50"), reserve_price=Decimal("100"), buy_it_now_price=Decimal("200"))
    )
    assert auction.buy_it_now_price == Decimal("200")


@pytest.mark.parametrize("buy_it_now_price", [Decimal("100"), Decimal("99.99")])
def test_auction_create_rejects_buy_it_now_at_or_below_reserve_even_if_above_starting(buy_it_now_price):
    """Exercises the SECOND half of buy_it_now's compound validator --
    above starting_price (50) but at-or-below reserve_price (100) must
    still be rejected."""
    with pytest.raises(ValidationError):
        AuctionCreate(
            **_kwargs(starting_price=Decimal("50"), reserve_price=Decimal("100"), buy_it_now_price=buy_it_now_price)
        )
