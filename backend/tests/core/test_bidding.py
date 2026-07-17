"""
White-box (statement/branch/condition) coverage for core/bidding.py.

Maps to AuctionEdge_Test_Plan.md section 2.1 (Tier 1 white-box targets) and
doubles as the Boundary Value Analysis table in section 2.3 — each boundary
below is parametrized at "one below / exactly at / one above" the threshold.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.core.bidding import (
    minimum_increment,
    minimum_next_bid,
    bid_meets_minimum,
    validate_bid,
    BidRejected,
    compute_new_end_time,
    is_reserve_met,
    determine_close_outcome,
    is_retractable,
    validate_buy_it_now,
    BuyItNowRejected,
    exceeds_active_bid_limit,
    resolve_tie,
    SOFT_CLOSE_WINDOW,
    SOFT_CLOSE_EXTENSION,
    RETRACTION_WINDOW,
    MAX_ACTIVE_BIDS_PER_USER,
)

NOW = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
SOME_USER = "user-a"
OTHER_USER = "user-b"


# --- minimum_increment / minimum_next_bid: tiered branch coverage ---

@pytest.mark.parametrize(
    "current_price, expected_increment",
    [
        (Decimal("0"), Decimal("1")),        # branch: < 50
        (Decimal("49.99"), Decimal("1")),    # boundary: just under 50
        (Decimal("50.00"), Decimal("5")),    # boundary: exactly 50 -> mid tier
        (Decimal("50.01"), Decimal("5")),    # boundary: just over 50
        (Decimal("249.99"), Decimal("5")),   # boundary: just under 250
        (Decimal("250.00"), Decimal("5")),   # boundary: exactly 250 -> still mid tier (<=)
        (Decimal("250.01"), Decimal("10")),  # boundary: just over 250 -> top tier
    ],
)
def test_minimum_increment_tiers(current_price, expected_increment):
    assert minimum_increment(current_price) == expected_increment


def test_minimum_next_bid_adds_increment_to_current_price():
    assert minimum_next_bid(Decimal("100")) == Decimal("105")


# --- bid_meets_minimum: the RQ2 mutation target (> vs >=) ---

@pytest.mark.parametrize(
    "bid_amount, required_min, expected",
    [
        (Decimal("99.99"), Decimal("100.00"), False),  # one cent below
        (Decimal("100.00"), Decimal("100.00"), True),  # exactly at minimum
        (Decimal("100.01"), Decimal("100.00"), True),  # one cent above
    ],
)
def test_bid_meets_minimum_boundary(bid_amount, required_min, expected):
    assert bid_meets_minimum(bid_amount, required_min) is expected


# --- validate_bid: branch coverage over 3a / 4a / 5a, in order ---

def _bid_kwargs(**overrides):
    kwargs = dict(
        bid_amount=Decimal("105"),
        current_price=Decimal("100"),
        current_highest_bidder_id=None,
        bidder_id=SOME_USER,
        auction_status="Active",
        auction_end_time=NOW + timedelta(minutes=10),
        now=NOW,
    )
    kwargs.update(overrides)
    return kwargs


def test_validate_bid_accepts_valid_bid():
    validate_bid(**_bid_kwargs())  # no exception


def test_validate_bid_rejects_non_active_status():
    with pytest.raises(BidRejected, match="already ended"):
        validate_bid(**_bid_kwargs(auction_status="Closed"))


def test_validate_bid_rejects_when_now_at_end_time_boundary():
    # now == auction_end_time: ">=" branch, auction must be treated as ended
    kwargs = _bid_kwargs(auction_end_time=NOW)
    with pytest.raises(BidRejected, match="already ended"):
        validate_bid(**kwargs)


def test_validate_bid_rejects_self_outbid():
    with pytest.raises(BidRejected, match="cannot outbid yourself"):
        validate_bid(**_bid_kwargs(current_highest_bidder_id=SOME_USER))


def test_validate_bid_allows_outbidding_someone_else():
    validate_bid(**_bid_kwargs(current_highest_bidder_id=OTHER_USER))  # no exception


def test_validate_bid_rejects_below_minimum_increment():
    with pytest.raises(BidRejected, match="Minimum bid"):
        validate_bid(**_bid_kwargs(bid_amount=Decimal("101")))  # min is 105


def test_validate_bid_accepts_exactly_minimum_increment():
    validate_bid(**_bid_kwargs(bid_amount=Decimal("105")))  # no exception


# --- compute_new_end_time: soft-close window branch ---

@pytest.mark.parametrize(
    "remaining, should_extend",
    [
        (timedelta(minutes=3, seconds=1), False),  # just outside window
        (timedelta(minutes=3), True),              # exactly at window boundary (<=)
        (timedelta(minutes=2, seconds=59), True),  # just inside window
    ],
)
def test_compute_new_end_time_soft_close_boundary(remaining, should_extend):
    end_time = NOW + remaining
    result = compute_new_end_time(end_time, NOW)
    if should_extend:
        assert result == end_time + SOFT_CLOSE_EXTENSION
    else:
        assert result == end_time


def test_compute_new_end_time_never_moves_end_time_earlier():
    end_time = NOW + timedelta(minutes=10)
    assert compute_new_end_time(end_time, NOW) >= end_time


# --- is_reserve_met ---

def test_is_reserve_met_no_reserve_price_always_true():
    assert is_reserve_met(None, Decimal("1")) is True


@pytest.mark.parametrize(
    "current_price, reserve_price, expected",
    [
        (Decimal("99.99"), Decimal("100.00"), False),
        (Decimal("100.00"), Decimal("100.00"), True),
        (Decimal("100.01"), Decimal("100.00"), True),
    ],
)
def test_is_reserve_met_boundary(current_price, reserve_price, expected):
    assert is_reserve_met(reserve_price, current_price) is expected


# --- determine_close_outcome: three-way branch ---

def test_determine_close_outcome_no_bids():
    assert determine_close_outcome(
        has_bids=False, reserve_price=Decimal("50"), current_price=Decimal("0")
    ) == "Unsold-NoBids"


def test_determine_close_outcome_no_bids_takes_priority_over_reserve():
    # has_bids=False must win even if current_price would otherwise satisfy reserve
    assert determine_close_outcome(
        has_bids=False, reserve_price=None, current_price=Decimal("0")
    ) == "Unsold-NoBids"


def test_determine_close_outcome_reserve_not_met():
    assert determine_close_outcome(
        has_bids=True, reserve_price=Decimal("100"), current_price=Decimal("99.99")
    ) == "Unsold-ReserveNotMet"


def test_determine_close_outcome_reserve_met_boundary():
    assert determine_close_outcome(
        has_bids=True, reserve_price=Decimal("100"), current_price=Decimal("100")
    ) == "Sold"


def test_determine_close_outcome_sold_no_reserve():
    assert determine_close_outcome(
        has_bids=True, reserve_price=None, current_price=Decimal("1")
    ) == "Sold"


# --- is_retractable: 15-minute hard window boundary ---

@pytest.mark.parametrize(
    "elapsed, expected",
    [
        (RETRACTION_WINDOW - timedelta(seconds=1), True),   # 14:59
        (RETRACTION_WINDOW, True),                           # 15:00 exactly (<=)
        (RETRACTION_WINDOW + timedelta(seconds=1), False),  # 15:01
    ],
)
def test_is_retractable_boundary(elapsed, expected):
    bid_timestamp = NOW - elapsed
    assert is_retractable(bid_timestamp, NOW) is expected


def test_is_retractable_is_monotonic_in_time():
    # Property (also exercised via Hypothesis in test_bidding_properties.py):
    # once false, must stay false as time moves further forward.
    bid_timestamp = NOW - RETRACTION_WINDOW - timedelta(seconds=1)
    assert is_retractable(bid_timestamp, NOW) is False
    assert is_retractable(bid_timestamp, NOW + timedelta(hours=1)) is False


# --- validate_buy_it_now ---

def _bin_kwargs(**overrides):
    kwargs = dict(
        buy_it_now_price=Decimal("500"),
        current_price=Decimal("100"),
        auction_status="Active",
        auction_end_time=NOW + timedelta(minutes=10),
        now=NOW,
    )
    kwargs.update(overrides)
    return kwargs


def test_validate_buy_it_now_accepts_when_available():
    validate_buy_it_now(**_bin_kwargs())  # no exception


def test_validate_buy_it_now_rejects_when_not_offered():
    with pytest.raises(BuyItNowRejected, match="does not offer"):
        validate_buy_it_now(**_bin_kwargs(buy_it_now_price=None))


def test_validate_buy_it_now_rejects_when_auction_ended():
    with pytest.raises(BuyItNowRejected, match="already ended"):
        validate_buy_it_now(**_bin_kwargs(auction_status="Closed"))


def test_validate_buy_it_now_rejects_when_current_price_at_bin_boundary():
    # current_price == buy_it_now_price: ">=" branch, BIN no longer available
    with pytest.raises(BuyItNowRejected, match="no longer available"):
        validate_buy_it_now(**_bin_kwargs(current_price=Decimal("500")))


def test_validate_buy_it_now_accepts_one_cent_below_bin_price():
    validate_buy_it_now(**_bin_kwargs(current_price=Decimal("499.99")))  # no exception


# --- exceeds_active_bid_limit: 5th succeeds, 6th fails ---

@pytest.mark.parametrize(
    "current_active_bid_count, expected",
    [
        (MAX_ACTIVE_BIDS_PER_USER - 2, False),  # 4th bid about to be placed -> allowed
        (MAX_ACTIVE_BIDS_PER_USER - 1, False),  # 5th bid about to be placed -> allowed
        (MAX_ACTIVE_BIDS_PER_USER, True),       # 6th bid about to be placed -> rejected
    ],
)
def test_exceeds_active_bid_limit_boundary(current_active_bid_count, expected):
    assert exceeds_active_bid_limit(current_active_bid_count) is expected


# --- resolve_tie ---

def test_resolve_tie_empty_list_raises():
    with pytest.raises(ValueError):
        resolve_tie([])


def test_resolve_tie_picks_first_and_is_deterministic():
    tied = ["bid-1", "bid-2", "bid-3"]
    assert resolve_tie(tied) == "bid-1"
    assert resolve_tie(tied) == resolve_tie(tied)


def test_resolve_tie_single_bid_returns_that_bid():
    assert resolve_tie(["only-bid"]) == "only-bid"
