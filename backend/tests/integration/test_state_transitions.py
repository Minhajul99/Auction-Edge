"""
State transition testing (plan section 4, Tier 3 -- light-touch by design):

    Auction status: Active -> Closed -> {Sold, Unsold, ReserveNotMet}

The pure-function rejection (validate_bid's "auction already ended" check)
is already covered in tests/core/test_bidding.py. This file adds just the
handful of end-to-end checks the plan calls for: confirming the real API
enforces the same transition when an auction is actually in a terminal
state, not just when the pure function is called directly.
"""

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
from app.core.auth import hash_password, create_access_token

from tests.integration.conftest import client


def _create_auction_in_status(status: str):
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
        Wallet(user_id=bidder.id, balance=Decimal("1000"), held_amount=Decimal("0")),
    ])

    item = Item(title="State Transition Test Item", description="d", category="Gaming", seller_id=seller.id)
    db.add(item)
    db.flush()

    auction = Auction(
        item_id=item.id, starting_price=Decimal("50"), reserve_price=None,
        current_price=Decimal("50"), start_time=now - timedelta(days=2),
        end_time=now - timedelta(days=1),  # already in the past regardless of status
        status=status,
    )
    db.add(auction)
    db.commit()

    ids = dict(auction_id=auction.id, item_id=item.id, seller_id=seller.id, bidder_id=bidder.id)
    db.close()
    return ids


def _cleanup(ids):
    db = SessionLocal()
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


@pytest.mark.parametrize("terminal_status", ["Closed", "Unsold-NoBids", "Unsold-ReserveNotMet"])
def test_bid_rejected_end_to_end_on_a_non_active_auction(terminal_status):
    ids = _create_auction_in_status(terminal_status)
    try:
        token = create_access_token(ids["bidder_id"])
        resp = client.post(
            f"/auctions/{ids['auction_id']}/bids",
            json={"amount": "100.00"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 400
        assert "ended" in resp.json()["detail"].lower()
    finally:
        _cleanup(ids)


def test_retract_rejected_end_to_end_on_a_closed_auction():
    """The retract endpoint has its own, separate terminal-status guard
    (api/bids.py's 'Closed auctions cannot be modified' check) -- a
    different transition than validate_bid's, worth its own case."""
    ids = _create_auction_in_status("Closed")
    try:
        token = create_access_token(ids["bidder_id"])
        resp = client.post(
            f"/auctions/{ids['auction_id']}/bids/{uuid.uuid4()}/retract",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 400
        assert "closed" in resp.json()["detail"].lower()
    finally:
        _cleanup(ids)
