"""
Property-based tests for core/bidding.py (RQ3, plan section 2.5).

These don't re-check specific boundary values (tests/core/test_bidding.py
already owns that) — they check that an invariant holds across a huge,
Hypothesis-generated input space, which is what makes this a distinct
technique from BVA rather than a restatement of it.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from hypothesis import given, strategies as st

from app.core.bidding import (
    bid_meets_minimum,
    minimum_next_bid,
    validate_bid,
    BidRejected,
    validate_buy_it_now,
    BuyItNowRejected,
    is_retractable,
    compute_new_end_time,
)

money = st.decimals(min_value="0", max_value="1000000", places=2, allow_nan=False, allow_infinity=False)
non_negative_timedelta = st.integers(min_value=0, max_value=60 * 24 * 30).map(lambda m: timedelta(minutes=m))
AUCTION_START = datetime(2026, 1, 1, tzinfo=timezone.utc)


@given(bid_amount=money, current_price=money)
def test_validate_bid_matches_bid_meets_minimum(bid_amount, current_price):
    """validate_bid's minimum-increment branch must agree with bid_meets_minimum
    for every (amount, current_price) pair — an inconsistency here would mean
    the two are checking different things despite validate_bid delegating to it."""
    required_min = minimum_next_bid(current_price)
    should_succeed = bid_meets_minimum(bid_amount, required_min)

    try:
        validate_bid(
            bid_amount=bid_amount,
            current_price=current_price,
            current_highest_bidder_id=None,
            bidder_id="bidder",
            auction_status="Active",
            auction_end_time=AUCTION_START + timedelta(days=1),
            now=AUCTION_START,
        )
        accepted = True
    except BidRejected:
        accepted = False

    assert accepted == should_succeed


@given(buy_it_now_price=money, current_price=money)
def test_validate_buy_it_now_never_accepts_at_or_above_bin_price(buy_it_now_price, current_price):
    """If a Buy It Now purchase is accepted, current_price must have been
    strictly below the BIN price — otherwise a buyer could 'complete' a BIN
    purchase for a price the auction already exceeded through normal bidding."""
    try:
        validate_buy_it_now(
            buy_it_now_price=buy_it_now_price,
            current_price=current_price,
            auction_status="Active",
            auction_end_time=AUCTION_START + timedelta(days=1),
            now=AUCTION_START,
        )
        accepted = True
    except BuyItNowRejected:
        accepted = False

    if accepted:
        assert current_price < buy_it_now_price


@given(elapsed_at_check=non_negative_timedelta, additional_wait=non_negative_timedelta)
def test_is_retractable_is_monotonic_in_time(elapsed_at_check, additional_wait):
    """Once a bid becomes non-retractable, it must stay non-retractable —
    time only moves forward, so the 15-minute window can't reopen."""
    bid_timestamp = AUCTION_START
    now = bid_timestamp + elapsed_at_check
    later = now + additional_wait

    if not is_retractable(bid_timestamp, now):
        assert not is_retractable(bid_timestamp, later)


@given(window_minutes=st.integers(min_value=0, max_value=60 * 24), bid_offset_minutes=st.integers(min_value=0, max_value=60 * 24))
def test_compute_new_end_time_never_moves_end_time_earlier(window_minutes, bid_offset_minutes):
    """The soft-close extension is the only thing that can change end_time,
    and it only ever pushes it later — a bid should never shorten an auction."""
    current_end_time = AUCTION_START + timedelta(minutes=window_minutes)
    bid_time = AUCTION_START + timedelta(minutes=bid_offset_minutes)

    new_end_time = compute_new_end_time(current_end_time, bid_time)

    assert new_end_time >= current_end_time
