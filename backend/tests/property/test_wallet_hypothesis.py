"""
Property-based tests for core/wallet.py (RQ3, plan section 2.5).

Complements tests/core/test_wallet.py's boundary values by checking the
wallet-hold invariant across a large generated space of balance/held/bid
combinations, rather than a handful of hand-picked ones.
"""

from decimal import Decimal

from hypothesis import given, strategies as st

from app.core.wallet import available_balance, has_sufficient_funds

money = st.decimals(min_value="0", max_value="1000000", places=2, allow_nan=False, allow_infinity=False)


@given(balance=money, held_amount=money, bid_amount=money)
def test_has_sufficient_funds_matches_available_balance_comparison(balance, held_amount, bid_amount):
    """has_sufficient_funds must agree with a direct (balance - held) >= bid_amount
    check for every input — a divergence here would mean the two definitions
    of 'available balance' have drifted apart."""
    assert has_sufficient_funds(balance, held_amount, bid_amount) == (
        available_balance(balance, held_amount) >= bid_amount
    )


@given(balance=money, held_amount=money, bid_amount=money)
def test_has_sufficient_funds_never_allows_available_balance_to_go_negative(balance, held_amount, bid_amount):
    """The core wallet invariant (held_amount <= balance, always): if a bid is
    approved, placing its hold cannot push the available balance below zero."""
    if has_sufficient_funds(balance, held_amount, bid_amount):
        assert available_balance(balance, held_amount) - bid_amount >= 0
