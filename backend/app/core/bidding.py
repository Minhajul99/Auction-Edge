"""
Core bidding logic for AuctionEdge.

Deliberately free of any DB or FastAPI imports — this module is pure Python
so it can be unit-tested, mutation-tested, and mapped to a TLA+ spec without
any infrastructure dependencies.
"""

from decimal import Decimal
from datetime import datetime, timedelta, timezone


# --- UC1: Minimum increment rules (tiered) ---

def minimum_increment(current_price: Decimal) -> Decimal:
    """Tiered increment: <$50 -> $1, $50-$250 -> $5, >$250 -> $10."""
    if current_price < 50:
        return Decimal("1")
    elif current_price <= 250:
        return Decimal("5")
    else:
        return Decimal("10")


def minimum_next_bid(current_price: Decimal) -> Decimal:
    return current_price + minimum_increment(current_price)


def bid_meets_minimum(bid_amount: Decimal, required_min: Decimal) -> bool:
    """
    Isolated comparison — the exact ">"/">=" operator your proposal names
    as a mutation-testing target (RQ2: mutating > to >=). Kept as its own
    one-line function, separate from validate_bid's control flow, so a
    mutation tool has a single unambiguous operator to flip and your test
    suite can target it directly (e.g. bid == required_min: True or False?).
    """
    return bid_amount >= required_min


class BidRejected(Exception):
    """Raised when a bid fails validation. Carries a client-facing reason."""
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


def validate_bid(
    *,
    bid_amount: Decimal,
    current_price: Decimal,
    current_highest_bidder_id,
    bidder_id,
    auction_status: str,
    auction_end_time: datetime,
    now: datetime,
) -> None:
    """
    Runs UC1's validation steps in order. Raises BidRejected on the first failure.
    Matches UC1 extensions 3a, 4a, 5a.
    """
    # 3a: auction already closed
    if auction_status != "Active" or now >= auction_end_time:
        raise BidRejected("Sorry, this auction has already ended!")

    # 4a: bidder is already the current highest bidder
    if current_highest_bidder_id is not None and bidder_id == current_highest_bidder_id:
        raise BidRejected("You cannot outbid yourself.")

    # 5a: bid does not meet minimum increment
    required_min = minimum_next_bid(current_price)
    if not bid_meets_minimum(bid_amount, required_min):
        raise BidRejected(f"Minimum bid is {required_min}.")


# --- UC1: Soft-close (anti-sniping) rule ---

SOFT_CLOSE_WINDOW = timedelta(minutes=3)
SOFT_CLOSE_EXTENSION = timedelta(minutes=5)


def compute_new_end_time(current_end_time: datetime, bid_time: datetime) -> datetime:
    """
    If the bid falls within the soft-close window (<=3 min remaining),
    extend the end time by 5 minutes. Otherwise, end time is unchanged.
    """
    remaining = current_end_time - bid_time
    if remaining <= SOFT_CLOSE_WINDOW:
        return current_end_time + SOFT_CLOSE_EXTENSION
    return current_end_time


# --- UC1: Reserve check ---

def is_reserve_met(reserve_price: Decimal | None, current_price: Decimal) -> bool:
    if reserve_price is None:
        return True
    return current_price >= reserve_price


# --- UC5: Auto-close outcome determination ---

def determine_close_outcome(
    *,
    has_bids: bool,
    reserve_price: Decimal | None,
    current_price: Decimal,
) -> str:
    """
    Given the final state of an auction at close time, determines the outcome.
    Returns one of: "Unsold-NoBids", "Unsold-ReserveNotMet", "Sold".
    """
    if not has_bids:
        return "Unsold-NoBids"
    if reserve_price is not None and current_price < reserve_price:
        return "Unsold-ReserveNotMet"
    return "Sold"


# --- UC3: Retraction window ---

RETRACTION_WINDOW = timedelta(minutes=15)


def is_retractable(bid_timestamp: datetime, now: datetime) -> bool:
    """Hard 15-minute limit measured from the original bid timestamp."""
    return (now - bid_timestamp) <= RETRACTION_WINDOW


# --- Buy It Now ---

class BuyItNowRejected(Exception):
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


def validate_buy_it_now(
    *,
    buy_it_now_price: Decimal | None,
    current_price: Decimal,
    auction_status: str,
    auction_end_time: datetime,
    now: datetime,
) -> None:
    """
    Validates a Buy It Now purchase attempt. A perfect state-transition
    testing target: on success, the caller transitions the auction straight
    to "Closed" (Sold), bypassing the timer entirely. Any standard bid that
    arrives after this must then be rejected (extension 3a in validate_bid
    already covers this, since auction_status will no longer be "Active").
    """
    if buy_it_now_price is None:
        raise BuyItNowRejected("This auction does not offer Buy It Now.")

    if auction_status != "Active" or now >= auction_end_time:
        raise BuyItNowRejected("Sorry, this auction has already ended!")

    if current_price >= buy_it_now_price:
        # Someone already bid at or above the BIN price through normal
        # bidding — BIN is no longer meaningful, the auction should be
        # left to resolve via normal soft-close/auto-close instead.
        raise BuyItNowRejected("Buy It Now is no longer available for this auction.")


# --- Bidder Account Limits ---

MAX_ACTIVE_BIDS_PER_USER = 5


def exceeds_active_bid_limit(current_active_bid_count: int) -> bool:
    """
    Isolated boundary check — bid #5 must succeed, bid #6 must fail.
    Kept as its own function so the exact boundary (< vs <=) is an
    explicit, easily mutation-tested unit, per the same rationale as
    bid_meets_minimum() above.
    """
    return current_active_bid_count >= MAX_ACTIVE_BIDS_PER_USER


# --- True-tie resolution (RQ1: race conditions "at the closing moment") ---

def resolve_tie(tied_bid_ids: list) -> object:
    """
    Given a list of bid identifiers that all share the exact same
    timestamp (a genuine, unresolvable-by-time tie — per your spec:
    "system arbitrarily accepts one, notifies the other"), deterministically
    picks a single winner.

    The rule itself is intentionally simple and arbitrary (first in the
    list wins) — the client's requirement only demands *a* consistent
    resolution, not a "fair" one. What matters for your TLA+ model and
    tests is that this function is:
      1. Total (always returns exactly one winner, never none/multiple)
      2. Deterministic (same input -> same output, every time)
      3. Isolated (no DB/timing dependency — pure function of the input list)

    Raises ValueError on an empty list, since "no bids" isn't a tie at all.
    """
    if not tied_bid_ids:
        raise ValueError("Cannot resolve a tie among zero bids.")
    return tied_bid_ids[0]
