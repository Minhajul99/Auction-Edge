"""
White-box (condition) coverage for core/wallet.py.

Maps to AuctionEdge_Test_Plan.md section 2.1 — condition coverage on
`balance - held >= amount`, and section 2.3's wallet-hold boundary
(available balance exactly equal to bid, and available - $0.01).
"""

from decimal import Decimal

import pytest

from app.core.wallet import (
    available_balance,
    has_sufficient_funds,
    InsufficientFunds,
)


def test_available_balance_is_balance_minus_held():
    assert available_balance(Decimal("100"), Decimal("40")) == Decimal("60")


def test_available_balance_can_be_zero():
    assert available_balance(Decimal("100"), Decimal("100")) == Decimal("0")


@pytest.mark.parametrize(
    "balance, held_amount, bid_amount, expected",
    [
        (Decimal("100"), Decimal("0"), Decimal("100.01"), False),  # one cent short
        (Decimal("100"), Decimal("0"), Decimal("100.00"), True),   # exactly equal
        (Decimal("100"), Decimal("0"), Decimal("99.99"), True),    # comfortably enough
        (Decimal("100"), Decimal("40"), Decimal("60.00"), True),   # held reduces availability, exact match
        (Decimal("100"), Decimal("40"), Decimal("60.01"), False),  # held reduces availability, one cent short
    ],
)
def test_has_sufficient_funds_boundary(balance, held_amount, bid_amount, expected):
    assert has_sufficient_funds(balance, held_amount, bid_amount) is expected


def test_has_sufficient_funds_double_spend_guard():
    # $100 balance, no prior hold: a first $100 bid succeeds...
    assert has_sufficient_funds(Decimal("100"), Decimal("0"), Decimal("100")) is True
    # ...but once that hold is recorded, a second concurrent $100 bid on a
    # different auction must fail — this is the invariant the wallet-hold
    # mechanism exists to protect (held_amount <= balance, always).
    assert has_sufficient_funds(Decimal("100"), Decimal("100"), Decimal("100")) is False


def test_insufficient_funds_exception_carries_amounts():
    exc = InsufficientFunds(available=Decimal("10"), required=Decimal("25"))
    assert exc.available == Decimal("10")
    assert exc.required == Decimal("25")
    assert "10" in str(exc)
    assert "25" in str(exc)
