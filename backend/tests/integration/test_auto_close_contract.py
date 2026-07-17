"""
Contract-based test for core/auto_close.py (plan section 2.4, row 3):

    Precondition: auction status = Active.
    Postcondition: exactly one closure event logged per auction, even
    under repeated sweep calls.

close_expired_auctions() opens its OWN database session internally
(SessionLocal()) rather than accepting one as a parameter, so it can't
share the rollback-wrapped db_session fixture the wallet contract tests
use (tests/integration/conftest.py) — a session on a different connection
wouldn't see uncommitted rows from this test's transaction. Instead, this
fixture commits real rows and deletes them again in teardown, in FK-safe
order (notifications and audit log entries before the rows they reference).
"""

import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.models.user import User
from app.models.wallet import Wallet
from app.models.item import Item
from app.models.auction import Auction
from app.models.bid import Bid
from app.models.audit_log import AuditLogEntry
from app.models.notification import Notification
from app.core.auth import hash_password
from app.core.auto_close import close_expired_auctions


def _create_expired_auction(*, reserve_price, current_price, bid_amount, held_amount):
    """Commits a seller, a bidder (with a wallet hold), an item, an already-
    expired Active auction, and one active bid at the given amount. Returns
    the IDs teardown needs to clean everything up again."""
    db: Session = SessionLocal()
    now = datetime.now(timezone.utc)

    seller = User(
        first_name="Seller", last_name="Test", email=f"{uuid.uuid4()}@example.test",
        password_hash=hash_password("x"),
    )
    bidder = User(
        first_name="Bidder", last_name="Test", email=f"{uuid.uuid4()}@example.test",
        password_hash=hash_password("x"),
    )
    db.add_all([seller, bidder])
    db.flush()

    db.add_all([
        Wallet(user_id=seller.id, balance=Decimal("0"), held_amount=Decimal("0")),
        Wallet(user_id=bidder.id, balance=Decimal("100"), held_amount=held_amount),
    ])

    item = Item(title="Auto-Close Test Item", description="d", category="Gaming", seller_id=seller.id)
    db.add(item)
    db.flush()

    auction = Auction(
        item_id=item.id,
        starting_price=Decimal("50"),
        reserve_price=reserve_price,
        current_price=current_price,
        start_time=now - timedelta(days=1),
        end_time=now - timedelta(minutes=1),  # already expired
        status="Active",
    )
    db.add(auction)
    db.flush()

    bid = Bid(
        auction_id=auction.id, bidder_id=bidder.id, amount=bid_amount,
        timestamp=now - timedelta(minutes=2), status="active",
    )
    db.add(bid)
    db.commit()

    ids = dict(
        auction_id=auction.id, item_id=item.id, bid_id=bid.id,
        seller_id=seller.id, bidder_id=bidder.id,
    )
    db.close()
    return ids


def _cleanup(ids: dict):
    db: Session = SessionLocal()
    db.query(Notification).filter(Notification.auction_id == ids["auction_id"]).delete()
    db.query(AuditLogEntry).filter(AuditLogEntry.entity_id == ids["auction_id"]).delete()
    db.query(Bid).filter(Bid.id == ids["bid_id"]).delete()
    db.query(Auction).filter(Auction.id == ids["auction_id"]).delete()
    db.query(Item).filter(Item.id == ids["item_id"]).delete()
    db.query(Wallet).filter(Wallet.user_id.in_([ids["seller_id"], ids["bidder_id"]])).delete(
        synchronize_session=False
    )
    db.query(User).filter(User.id.in_([ids["seller_id"], ids["bidder_id"]])).delete(
        synchronize_session=False
    )
    db.commit()
    db.close()


@pytest.fixture
def sold_auction():
    ids = _create_expired_auction(
        reserve_price=None, current_price=Decimal("60"),
        bid_amount=Decimal("60"), held_amount=Decimal("60"),
    )
    yield ids
    _cleanup(ids)


@pytest.fixture
def reserve_not_met_auction():
    ids = _create_expired_auction(
        reserve_price=Decimal("100"), current_price=Decimal("60"),
        bid_amount=Decimal("60"), held_amount=Decimal("60"),
    )
    yield ids
    _cleanup(ids)


def _closure_log_count(auction_id) -> int:
    db = SessionLocal()
    count = (
        db.query(AuditLogEntry)
        .filter(AuditLogEntry.entity_id == auction_id, AuditLogEntry.action == "auction_closed")
        .count()
    )
    db.close()
    return count


def test_auto_close_is_idempotent_under_repeated_sweeps(sold_auction):
    auction_id = sold_auction["auction_id"]

    asyncio.run(close_expired_auctions())

    db = SessionLocal()
    auction = db.get(Auction, auction_id)
    assert auction.status == "Closed"  # determine_close_outcome's "Sold" maps to status "Closed"
    db.close()
    assert _closure_log_count(auction_id) == 1

    # Simulate an overlapping/duplicate sweep (e.g. a scheduler retry) —
    # the auction is no longer "Active", so this must be a no-op.
    asyncio.run(close_expired_auctions())

    db = SessionLocal()
    auction_after = db.get(Auction, auction_id)
    assert auction_after.status == "Closed"
    db.close()
    assert _closure_log_count(auction_id) == 1  # not 2 -- idempotency postcondition


def _create_expired_auction_with_multiple_bidders():
    """One seller, one winner (leading active bid), two losing bidders
    (already-outbid bids) -- for the notification fan-out test below
    (plan section 3.2: auto-close sweep -> notification fan-out)."""
    db: Session = SessionLocal()
    now = datetime.now(timezone.utc)

    seller = User(
        first_name="Seller", last_name="Test", email=f"{uuid.uuid4()}@example.test",
        password_hash=hash_password("x"),
    )
    winner = User(
        first_name="Winner", last_name="Test", email=f"{uuid.uuid4()}@example.test",
        password_hash=hash_password("x"),
    )
    loser_1 = User(
        first_name="Loser1", last_name="Test", email=f"{uuid.uuid4()}@example.test",
        password_hash=hash_password("x"),
    )
    loser_2 = User(
        first_name="Loser2", last_name="Test", email=f"{uuid.uuid4()}@example.test",
        password_hash=hash_password("x"),
    )
    db.add_all([seller, winner, loser_1, loser_2])
    db.flush()

    db.add_all([
        Wallet(user_id=seller.id, balance=Decimal("0"), held_amount=Decimal("0")),
        Wallet(user_id=winner.id, balance=Decimal("100"), held_amount=Decimal("70")),
        Wallet(user_id=loser_1.id, balance=Decimal("100"), held_amount=Decimal("0")),
        Wallet(user_id=loser_2.id, balance=Decimal("100"), held_amount=Decimal("0")),
    ])

    item = Item(title="Auto-Close Fan-Out Item", description="d", category="Gaming", seller_id=seller.id)
    db.add(item)
    db.flush()

    auction = Auction(
        item_id=item.id, starting_price=Decimal("50"), reserve_price=None,
        current_price=Decimal("70"), start_time=now - timedelta(days=1),
        end_time=now - timedelta(minutes=1), status="Active",
    )
    db.add(auction)
    db.flush()

    db.add_all([
        Bid(auction_id=auction.id, bidder_id=winner.id, amount=Decimal("70"),
            timestamp=now - timedelta(minutes=1), status="active"),
        Bid(auction_id=auction.id, bidder_id=loser_1.id, amount=Decimal("60"),
            timestamp=now - timedelta(minutes=5), status="outbid"),
        Bid(auction_id=auction.id, bidder_id=loser_2.id, amount=Decimal("55"),
            timestamp=now - timedelta(minutes=10), status="outbid"),
    ])
    db.commit()

    ids = dict(
        auction_id=auction.id, item_id=item.id, seller_id=seller.id,
        winner_id=winner.id, loser_ids=[loser_1.id, loser_2.id],
    )
    db.close()
    return ids


def _cleanup_multi(ids: dict):
    db: Session = SessionLocal()
    all_user_ids = [ids["seller_id"], ids["winner_id"], *ids["loser_ids"]]
    db.query(Notification).filter(Notification.auction_id == ids["auction_id"]).delete()
    db.query(AuditLogEntry).filter(AuditLogEntry.entity_id == ids["auction_id"]).delete()
    db.query(Bid).filter(Bid.auction_id == ids["auction_id"]).delete()
    db.query(Auction).filter(Auction.id == ids["auction_id"]).delete()
    db.query(Item).filter(Item.id == ids["item_id"]).delete()
    db.query(Wallet).filter(Wallet.user_id.in_(all_user_ids)).delete(synchronize_session=False)
    db.query(User).filter(User.id.in_(all_user_ids)).delete(synchronize_session=False)
    db.commit()
    db.close()


@pytest.fixture
def sold_auction_with_losers():
    ids = _create_expired_auction_with_multiple_bidders()
    yield ids
    _cleanup_multi(ids)


def test_auto_close_notification_fan_out_reaches_winner_seller_and_losers(sold_auction_with_losers):
    ids = sold_auction_with_losers
    asyncio.run(close_expired_auctions())

    db = SessionLocal()

    def notification_types_for(user_id):
        return {
            n.type
            for n in db.query(Notification)
            .filter(Notification.user_id == user_id, Notification.auction_id == ids["auction_id"])
            .all()
        }

    assert notification_types_for(ids["winner_id"]) == {"won"}
    assert notification_types_for(ids["seller_id"]) == {"seller_auction_closed"}
    for loser_id in ids["loser_ids"]:
        assert notification_types_for(loser_id) == {"lost"}
    db.close()


def test_auto_close_releases_wallet_hold_exactly_once_on_reserve_not_met(reserve_not_met_auction):
    bidder_id = reserve_not_met_auction["bidder_id"]
    auction_id = reserve_not_met_auction["auction_id"]

    asyncio.run(close_expired_auctions())

    db = SessionLocal()
    wallet = db.query(Wallet).filter(Wallet.user_id == bidder_id).first()
    assert wallet.held_amount == Decimal("0.00")
    db.close()

    # Repeated sweep must not re-release (and, via the max(held - amount, 0)
    # clamp in release_hold, must not silently mask a double-release either).
    asyncio.run(close_expired_auctions())

    db = SessionLocal()
    wallet_after = db.query(Wallet).filter(Wallet.user_id == bidder_id).first()
    assert wallet_after.held_amount == Decimal("0.00")
    db.close()
    assert _closure_log_count(auction_id) == 1
