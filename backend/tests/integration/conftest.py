"""
Fixtures for contract-based / integration tests that need a real Postgres
connection (row locking, transaction semantics) rather than pure functions.

db_session wraps each test in its own transaction that is always rolled
back at teardown, so these tests can create whatever data they need
without leaving anything behind in the shared dev database.
"""

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.db.database import engine, SessionLocal
from app.models.user import User
from app.models.wallet import Wallet
from app.models.item import Item
from app.models.auction import Auction
from app.models.bid import Bid
from app.models.notification import Notification
from app.models.audit_log import AuditLogEntry
from app.core.auth import hash_password


@pytest.fixture
def db_session():
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def make_user_with_wallet(db_session):
    def _make(balance=Decimal("100.00"), held_amount=Decimal("0.00")):
        user = User(
            first_name="Test",
            last_name="User",
            email=f"{uuid.uuid4()}@example.test",
            password_hash=hash_password("irrelevant"),
        )
        db_session.add(user)
        db_session.flush()
        wallet = Wallet(user_id=user.id, balance=balance, held_amount=held_amount)
        db_session.add(wallet)
        db_session.flush()
        return user, wallet

    return _make


@pytest.fixture
def make_auction(db_session, make_user_with_wallet):
    def _make(
        *,
        reserve_price=None,
        current_price=Decimal("50.00"),
        starting_price=Decimal("50.00"),
        status="Active",
        end_time=None,
        buy_it_now_price=None,
        seller=None,
    ):
        if seller is None:
            seller, _ = make_user_with_wallet()
        item = Item(title="Test Item", description="d", category="Gaming", seller_id=seller.id)
        db_session.add(item)
        db_session.flush()
        now = datetime.now(timezone.utc)
        auction = Auction(
            item_id=item.id,
            starting_price=starting_price,
            reserve_price=reserve_price,
            current_price=current_price,
            start_time=now - timedelta(days=1),
            end_time=end_time or (now + timedelta(days=1)),
            status=status,
            buy_it_now_price=buy_it_now_price,
        )
        db_session.add(auction)
        db_session.flush()
        return item, auction

    return _make


# --- HTTP-level fixtures (used by tests that go through the real API) ---
#
# TestClient requests hit endpoints that open their OWN DB session per
# request (via the get_db dependency), so -- same as auto_close's tests --
# these commit real rows and clean them up afterward rather than relying
# on the rollback trick above.

client = TestClient(app)


@pytest.fixture
def bid_scenario():
    """One seller, two bidders (each with a $1000 wallet), one Active
    auction with no reserve, current_price=$50."""
    db = SessionLocal()
    seller = User(
        first_name="Seller", last_name="Test", email=f"{uuid.uuid4()}@example.test",
        password_hash=hash_password("x"),
    )
    bidder_1 = User(
        first_name="Bidder1", last_name="Test", email=f"{uuid.uuid4()}@example.test",
        password_hash=hash_password("x"),
    )
    bidder_2 = User(
        first_name="Bidder2", last_name="Test", email=f"{uuid.uuid4()}@example.test",
        password_hash=hash_password("x"),
    )
    db.add_all([seller, bidder_1, bidder_2])
    db.flush()
    db.add_all([
        Wallet(user_id=seller.id, balance=Decimal("0"), held_amount=Decimal("0")),
        Wallet(user_id=bidder_1.id, balance=Decimal("1000.00"), held_amount=Decimal("0")),
        Wallet(user_id=bidder_2.id, balance=Decimal("1000.00"), held_amount=Decimal("0")),
    ])

    item = Item(title="Integration Test Item", description="d", category="Gaming", seller_id=seller.id)
    other_item = Item(title="Unrelated Auction Item", description="d", category="Gaming", seller_id=seller.id)
    db.add_all([item, other_item])
    db.flush()

    now = datetime.now(timezone.utc)
    auction = Auction(
        item_id=item.id, starting_price=Decimal("50.00"), reserve_price=None,
        current_price=Decimal("50.00"), start_time=now - timedelta(hours=1),
        end_time=now + timedelta(hours=1), status="Active",
    )
    # A second, unrelated Active auction -- used to confirm WebSocket
    # broadcasts are correctly scoped per-auction (a client watching this
    # one must not see the first auction's bid events).
    other_auction = Auction(
        item_id=other_item.id, starting_price=Decimal("50.00"), reserve_price=None,
        current_price=Decimal("50.00"), start_time=now - timedelta(hours=1),
        end_time=now + timedelta(hours=1), status="Active",
    )
    db.add_all([auction, other_auction])
    db.commit()

    ids = dict(
        seller_id=seller.id, bidder_1_id=bidder_1.id, bidder_2_id=bidder_2.id,
        item_id=item.id, auction_id=auction.id,
        other_item_id=other_item.id, other_auction_id=other_auction.id,
    )
    db.close()

    yield ids

    cleanup_db = SessionLocal()
    user_ids = [ids["seller_id"], ids["bidder_1_id"], ids["bidder_2_id"]]
    auction_ids = [ids["auction_id"], ids["other_auction_id"]]
    item_ids = [ids["item_id"], ids["other_item_id"]]
    cleanup_db.query(Notification).filter(Notification.auction_id.in_(auction_ids)).delete(synchronize_session=False)
    cleanup_db.query(AuditLogEntry).filter(AuditLogEntry.user_id.in_(user_ids)).delete(synchronize_session=False)
    cleanup_db.query(Bid).filter(Bid.auction_id.in_(auction_ids)).delete(synchronize_session=False)
    cleanup_db.query(Auction).filter(Auction.id.in_(auction_ids)).delete(synchronize_session=False)
    cleanup_db.query(Item).filter(Item.id.in_(item_ids)).delete(synchronize_session=False)
    cleanup_db.query(Wallet).filter(Wallet.user_id.in_(user_ids)).delete(synchronize_session=False)
    cleanup_db.query(User).filter(User.id.in_(user_ids)).delete(synchronize_session=False)
    cleanup_db.commit()
    cleanup_db.close()
