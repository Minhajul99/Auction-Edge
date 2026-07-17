"""
Contract-based test for core/wallet_db.py (plan section 2.4, row 1):

    INVARIANT: held_amount <= balance, always, for every user.

Runs against a real Postgres connection (db_session fixture in conftest.py)
so the row-locking path in wallet_db.py is exercised for real, not just the
pure comparison in core/wallet.py that tests/core/test_wallet.py already
covers — this tier checks the invariant holds in the actual running system.
"""

from decimal import Decimal

import pytest

from app.core.wallet import InsufficientFunds
from app.core.wallet_db import (
    lock_wallets_in_order,
    place_hold,
    release_hold,
    finalize_charge,
    ensure_can_hold,
)


def _assert_invariant(wallet):
    assert wallet.held_amount <= wallet.balance


def test_invariant_holds_after_successful_hold(db_session, make_user_with_wallet):
    user, _wallet = make_user_with_wallet(balance=Decimal("100.00"))
    locked = lock_wallets_in_order(db_session, [user.id])[user.id]

    ensure_can_hold(locked, Decimal("100.00"))
    place_hold(locked, Decimal("100.00"))

    _assert_invariant(locked)
    assert locked.held_amount == Decimal("100.00")


def test_invariant_holds_after_rejected_hold(db_session, make_user_with_wallet):
    user, _wallet = make_user_with_wallet(balance=Decimal("100.00"), held_amount=Decimal("100.00"))
    locked = lock_wallets_in_order(db_session, [user.id])[user.id]

    with pytest.raises(InsufficientFunds):
        ensure_can_hold(locked, Decimal("0.01"))

    _assert_invariant(locked)  # a rejected hold must not have mutated state


def test_invariant_holds_through_hold_then_release_cycle(db_session, make_user_with_wallet):
    user, _wallet = make_user_with_wallet(balance=Decimal("200.00"))
    locked = lock_wallets_in_order(db_session, [user.id])[user.id]

    place_hold(locked, Decimal("150.00"))
    _assert_invariant(locked)

    release_hold(locked, Decimal("150.00"))
    _assert_invariant(locked)
    assert locked.held_amount == Decimal("0.00")


def test_invariant_holds_after_finalize_charge(db_session, make_user_with_wallet):
    user, _wallet = make_user_with_wallet(balance=Decimal("200.00"))
    locked = lock_wallets_in_order(db_session, [user.id])[user.id]

    place_hold(locked, Decimal("150.00"))
    finalize_charge(locked, Decimal("150.00"))

    _assert_invariant(locked)
    assert locked.balance == Decimal("50.00")
    assert locked.held_amount == Decimal("0.00")


def test_invariant_holds_across_two_users_locked_together(db_session, make_user_with_wallet):
    """The double-spend scenario from wallet.py's own docstring: two
    different users' wallets locked and touched in the same transaction,
    exercising lock_wallets_in_order's fixed lock ordering."""
    user_a, _ = make_user_with_wallet(balance=Decimal("100.00"))
    user_b, _ = make_user_with_wallet(balance=Decimal("50.00"))

    wallets = lock_wallets_in_order(db_session, [user_a.id, user_b.id])
    place_hold(wallets[user_a.id], Decimal("100.00"))
    place_hold(wallets[user_b.id], Decimal("50.00"))

    _assert_invariant(wallets[user_a.id])
    _assert_invariant(wallets[user_b.id])
