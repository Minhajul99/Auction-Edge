"""
Wallet DB operations. Separate from core/wallet.py (which is pure logic)
because these functions touch the database — kept together here so every
caller uses the same locking discipline.
"""

import uuid
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from app.models.wallet import Wallet
from app.core.wallet import has_sufficient_funds, InsufficientFunds


def lock_wallets_in_order(db: Session, user_ids: list) -> dict:
    """
    Locks (SELECT ... FOR UPDATE) the wallets for the given user IDs, in a
    FIXED order (sorted by user_id), regardless of the order they're
    passed in.

    WHY THIS MATTERS: a single bid transaction can need to lock two
    different wallets at once (the new bidder's, and the previous highest
    bidder's, if being outbid). If two concurrent transactions each try to
    lock "my wallet first, then theirs" using whatever order they happen
    to process users in, you get a classic deadlock: transaction A holds
    wallet 1 and waits for wallet 2, while transaction B holds wallet 2
    and waits for wallet 1 — neither can proceed.

    Always acquiring locks in the same GLOBAL order (sorted by user_id)
    eliminates this: every transaction that needs both wallets tries to
    lock the lower-sorted one first, so they queue behind each other
    instead of deadlocking.

    Returns a dict {user_id: Wallet}.
    """
    unique_ids = sorted(set(user_ids), key=str)
    wallets = (
        db.query(Wallet)
        .filter(Wallet.user_id.in_(unique_ids))
        .with_for_update()
        .all()
    )
    return {w.user_id: w for w in wallets}


def place_hold(wallet: Wallet, amount: Decimal) -> None:
    """
    Freezes `amount` of the wallet's available balance. Caller MUST have
    already locked this wallet row (see lock_wallets_in_order) and MUST
    have already verified has_sufficient_funds — this function does not
    re-check, to keep it a simple, obvious state mutation for testing.
    """
    wallet.held_amount = wallet.held_amount + amount


def release_hold(wallet: Wallet, amount: Decimal) -> None:
    """
    Unfreezes `amount` — called when a bid is outbid, retracted, admin-
    cancelled, or when an auction closes unsold while still holding the
    (former) leading bid's funds.
    """
    wallet.held_amount = max(wallet.held_amount - amount, Decimal("0"))


def finalize_charge(wallet: Wallet, amount: Decimal) -> None:
    """
    Converts a held amount into an actual charge — called only when the
    winner clicks Pay Now. Both balance and held_amount decrease by the
    same amount, since the funds were already frozen (held), not spent.
    """
    wallet.balance = wallet.balance - amount
    wallet.held_amount = max(wallet.held_amount - amount, Decimal("0"))


def ensure_can_hold(wallet: Wallet, amount: Decimal) -> None:
    """Raises InsufficientFunds if placing this hold would violate the invariant."""
    if not has_sufficient_funds(wallet.balance, wallet.held_amount, amount):
        available = wallet.balance - wallet.held_amount
        raise InsufficientFunds(available=available, required=amount)
