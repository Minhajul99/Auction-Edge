"""
Core wallet/bid-hold logic for AuctionEdge.

Pure Python, no DB/FastAPI imports — same isolation philosophy as
core/bidding.py, so this is directly unit-testable and mutation-testable.

The wallet introduces the project's second concurrency-critical invariant,
alongside "no lost bid updates":

    INVARIANT: for every user, at all times,
        held_amount <= balance
    (equivalently: available_balance >= 0, always)

This must hold even under the classic "double-spend" scenario: a user
with $100 attempting to place two $100 bids on two different auctions at
the exact same instant. Exactly one must succeed.
"""

from decimal import Decimal


def available_balance(balance: Decimal, held_amount: Decimal) -> Decimal:
    return balance - held_amount


def has_sufficient_funds(balance: Decimal, held_amount: Decimal, bid_amount: Decimal) -> bool:
    """
    Isolated comparison — the double-spend guard. Deliberately a single
    boundary check (>=), separate from any calling logic, so it's an
    obvious mutation-testing target (RQ2) and easy to unit test at the
    exact boundary: available == bid_amount must succeed, available ==
    bid_amount - 0.01 must fail.
    """
    return available_balance(balance, held_amount) >= bid_amount


class InsufficientFunds(Exception):
    def __init__(self, available: Decimal, required: Decimal):
        self.available = available
        self.required = required
        super().__init__(
            f"Insufficient funds: available {available}, required {required}"
        )
