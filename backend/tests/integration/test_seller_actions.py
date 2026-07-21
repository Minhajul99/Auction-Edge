"""
HTTP-level contract tests for the seller-action endpoints that had no
dedicated test coverage: accept-bid, cancel, pay, relist, buy-it-now.

Each test drives the real FastAPI app through TestClient (same pattern as
test_state_transitions.py) rather than calling the route functions
directly, so permission checks, status-code mapping, and the DB side
effects (wallet holds, notifications, status transitions) are all
exercised exactly as a real client would hit them.
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
from app.models.bid import Bid
from app.models.notification import Notification
from app.models.audit_log import AuditLogEntry
from app.core.auth import hash_password, create_access_token

from tests.integration.conftest import client


def _make_scenario(*, status="Active", with_bid=False, buy_it_now_price=None,
                    current_price=Decimal("50.00"), bidder_balance=Decimal("1000.00")):
    """Seller + (optional) bidder, one auction in the given status, and an
    optional active bid from the bidder at current_price."""
    db: Session = SessionLocal()
    now = datetime.now(timezone.utc)

    seller = User(
        first_name="Seller", last_name="Test", email=f"{uuid.uuid4()}@example.test",
        password_hash=hash_password("x"),
    )
    other_user = User(
        first_name="Other", last_name="Test", email=f"{uuid.uuid4()}@example.test",
        password_hash=hash_password("x"),
    )
    bidder = User(
        first_name="Bidder", last_name="Test", email=f"{uuid.uuid4()}@example.test",
        password_hash=hash_password("x"),
    )
    db.add_all([seller, other_user, bidder])
    db.flush()
    db.add_all([
        Wallet(user_id=seller.id, balance=Decimal("0"), held_amount=Decimal("0")),
        Wallet(user_id=other_user.id, balance=Decimal("1000"), held_amount=Decimal("0")),
        Wallet(user_id=bidder.id, balance=bidder_balance,
               held_amount=(current_price if with_bid else Decimal("0"))),
    ])

    item = Item(title="Seller Action Test Item", description="d", category="Gaming", seller_id=seller.id)
    db.add(item)
    db.flush()

    auction = Auction(
        item_id=item.id, starting_price=Decimal("50"), reserve_price=None,
        current_price=current_price,
        start_time=now - timedelta(days=1),
        end_time=now + timedelta(days=1) if status == "Active" else now - timedelta(hours=1),
        status=status,
        buy_it_now_price=buy_it_now_price,
    )
    db.add(auction)
    db.flush()

    bid = None
    if with_bid:
        bid = Bid(
            auction_id=auction.id, bidder_id=bidder.id, amount=current_price,
            timestamp=now, status="active",
        )
        db.add(bid)
        db.flush()

    db.commit()

    ids = dict(
        auction_id=auction.id, item_id=item.id,
        seller_id=seller.id, other_user_id=other_user.id, bidder_id=bidder.id,
        bid_id=bid.id if bid else None,
    )
    db.close()
    return ids


def _cleanup(ids):
    db = SessionLocal()
    user_ids = [ids["seller_id"], ids["other_user_id"], ids["bidder_id"]]
    auction_ids = [ids["auction_id"]]
    db.query(Notification).filter(Notification.auction_id.in_(auction_ids)).delete(synchronize_session=False)
    db.query(AuditLogEntry).filter(
        (AuditLogEntry.entity_id.in_(auction_ids)) | (AuditLogEntry.user_id.in_(user_ids))
    ).delete(synchronize_session=False)
    db.query(Bid).filter(Bid.auction_id.in_(auction_ids)).delete(synchronize_session=False)
    db.query(Auction).filter(Auction.id.in_(auction_ids)).delete(synchronize_session=False)
    db.query(Item).filter(Item.id == ids["item_id"]).delete(synchronize_session=False)
    db.query(Wallet).filter(Wallet.user_id.in_(user_ids)).delete(synchronize_session=False)
    db.query(User).filter(User.id.in_(user_ids)).delete(synchronize_session=False)
    db.commit()
    db.close()


def _wallet(user_id):
    db = SessionLocal()
    w = db.query(Wallet).filter(Wallet.user_id == user_id).first()
    db.expunge(w)
    db.close()
    return w


def _make_lone_user():
    """A real, persisted user with no auctions -- get_current_user looks
    the user up in the DB, so a token for a random, never-registered UUID
    fails with 401 before the route body even runs. These 404 tests need
    a genuine user to get past auth and reach the auction lookup."""
    db = SessionLocal()
    user = User(
        first_name="Lone", last_name="User", email=f"{uuid.uuid4()}@example.test",
        password_hash=hash_password("x"),
    )
    db.add(user)
    db.commit()
    user_id = user.id
    db.close()
    return user_id


def _cleanup_lone_user(user_id):
    db = SessionLocal()
    db.query(User).filter(User.id == user_id).delete()
    db.commit()
    db.close()


# --------------------------------------------------------------------- #
# accept-bid
# --------------------------------------------------------------------- #

def test_accept_bid_closes_auction_and_notifies_winner():
    ids = _make_scenario(with_bid=True)
    try:
        token = create_access_token(ids["seller_id"])
        resp = client.post(
            f"/auctions/{ids['auction_id']}/accept-bid",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "Closed"

        db = SessionLocal()
        won_notification = (
            db.query(Notification)
            .filter(
                Notification.user_id == ids["bidder_id"],
                Notification.auction_id == ids["auction_id"],
                Notification.type == "won",
            )
            .count()
        )
        db.close()
        assert won_notification == 1
    finally:
        _cleanup(ids)


def test_accept_bid_rejected_for_non_seller():
    ids = _make_scenario(with_bid=True)
    try:
        token = create_access_token(ids["other_user_id"])
        resp = client.post(
            f"/auctions/{ids['auction_id']}/accept-bid",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403
    finally:
        _cleanup(ids)


def test_accept_bid_rejected_when_no_active_bids():
    ids = _make_scenario(with_bid=False)
    try:
        token = create_access_token(ids["seller_id"])
        resp = client.post(
            f"/auctions/{ids['auction_id']}/accept-bid",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 400
        assert "no active bids" in resp.json()["detail"].lower()
    finally:
        _cleanup(ids)


def test_accept_bid_rejected_when_auction_not_active():
    ids = _make_scenario(status="Closed", with_bid=True)
    try:
        token = create_access_token(ids["seller_id"])
        resp = client.post(
            f"/auctions/{ids['auction_id']}/accept-bid",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 400
        assert "not currently active" in resp.json()["detail"].lower()
    finally:
        _cleanup(ids)


def test_accept_bid_returns_404_for_unknown_auction():
    user_id = _make_lone_user()
    try:
        token = create_access_token(user_id)
        resp = client.post(
            f"/auctions/{uuid.uuid4()}/accept-bid",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404
    finally:
        _cleanup_lone_user(user_id)


# --------------------------------------------------------------------- #
# cancel
# --------------------------------------------------------------------- #

def test_cancel_releases_hold_and_notifies_bidder():
    ids = _make_scenario(with_bid=True)
    try:
        token = create_access_token(ids["seller_id"])
        resp = client.post(
            f"/auctions/{ids['auction_id']}/cancel",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "Cancelled"

        wallet = _wallet(ids["bidder_id"])
        assert wallet.held_amount == Decimal("0.00")

        db = SessionLocal()
        cancelled_notification = (
            db.query(Notification)
            .filter(
                Notification.user_id == ids["bidder_id"],
                Notification.auction_id == ids["auction_id"],
                Notification.type == "auction_cancelled",
            )
            .count()
        )
        db.close()
        assert cancelled_notification == 1
    finally:
        _cleanup(ids)


def test_cancel_with_no_bids_is_a_no_op_besides_status():
    ids = _make_scenario(with_bid=False)
    try:
        token = create_access_token(ids["seller_id"])
        resp = client.post(
            f"/auctions/{ids['auction_id']}/cancel",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "Cancelled"
    finally:
        _cleanup(ids)


def test_cancel_rejected_for_non_seller():
    ids = _make_scenario(with_bid=True)
    try:
        token = create_access_token(ids["other_user_id"])
        resp = client.post(
            f"/auctions/{ids['auction_id']}/cancel",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

        wallet = _wallet(ids["bidder_id"])
        assert wallet.held_amount == Decimal("50.00")  # untouched
    finally:
        _cleanup(ids)


def test_cancel_rejected_when_auction_not_active():
    ids = _make_scenario(status="Unsold-NoBids")
    try:
        token = create_access_token(ids["seller_id"])
        resp = client.post(
            f"/auctions/{ids['auction_id']}/cancel",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 400
        assert "only an active auction" in resp.json()["detail"].lower()
    finally:
        _cleanup(ids)


def test_cancel_returns_404_for_unknown_auction():
    user_id = _make_lone_user()
    try:
        token = create_access_token(user_id)
        resp = client.post(
            f"/auctions/{uuid.uuid4()}/cancel",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404
    finally:
        _cleanup_lone_user(user_id)


# --------------------------------------------------------------------- #
# pay
# --------------------------------------------------------------------- #

def test_pay_charges_winning_bidder_and_marks_paid():
    ids = _make_scenario(status="Closed", with_bid=True, current_price=Decimal("55.00"))
    try:
        token = create_access_token(ids["bidder_id"])
        resp = client.post(
            f"/auctions/{ids['auction_id']}/pay",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["payment_status"] == "paid"

        wallet = _wallet(ids["bidder_id"])
        assert wallet.balance == Decimal("945.00")  # 1000 - 55
        assert wallet.held_amount == Decimal("0.00")
    finally:
        _cleanup(ids)


def test_pay_rejected_for_non_winning_bidder():
    ids = _make_scenario(status="Closed", with_bid=True)
    try:
        token = create_access_token(ids["other_user_id"])
        resp = client.post(
            f"/auctions/{ids['auction_id']}/pay",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403
    finally:
        _cleanup(ids)


def test_pay_rejected_when_auction_not_closed():
    ids = _make_scenario(status="Active", with_bid=True)
    try:
        token = create_access_token(ids["bidder_id"])
        resp = client.post(
            f"/auctions/{ids['auction_id']}/pay",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 400
        assert "no winner to pay for" in resp.json()["detail"].lower()
    finally:
        _cleanup(ids)


def test_pay_rejected_when_already_paid():
    ids = _make_scenario(status="Closed", with_bid=True, current_price=Decimal("55.00"))
    try:
        token = create_access_token(ids["bidder_id"])
        first = client.post(
            f"/auctions/{ids['auction_id']}/pay",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert first.status_code == 200

        second = client.post(
            f"/auctions/{ids['auction_id']}/pay",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert second.status_code == 400
        assert "already been paid" in second.json()["detail"].lower()
    finally:
        _cleanup(ids)


def test_pay_returns_404_for_unknown_auction():
    user_id = _make_lone_user()
    try:
        token = create_access_token(user_id)
        resp = client.post(
            f"/auctions/{uuid.uuid4()}/pay",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404
    finally:
        _cleanup_lone_user(user_id)


# --------------------------------------------------------------------- #
# relist
# --------------------------------------------------------------------- #

def test_relist_creates_new_active_auction_for_same_item():
    ids = _make_scenario(status="Unsold-NoBids")
    new_auction_id = None
    try:
        token = create_access_token(ids["seller_id"])
        resp = client.post(
            f"/auctions/{ids['auction_id']}/relist",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 201
        body = resp.json()
        new_auction_id = uuid.UUID(body["id"])
        assert new_auction_id != ids["auction_id"]
        assert body["status"] == "Active"
        assert body["item_id"] == str(ids["item_id"])
    finally:
        if new_auction_id:
            db = SessionLocal()
            db.query(Auction).filter(Auction.id == new_auction_id).delete()
            db.commit()
            db.close()
        _cleanup(ids)


def test_relist_rejected_for_non_seller():
    ids = _make_scenario(status="Unsold-NoBids")
    try:
        token = create_access_token(ids["other_user_id"])
        resp = client.post(
            f"/auctions/{ids['auction_id']}/relist",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403
    finally:
        _cleanup(ids)


def test_relist_rejected_when_old_auction_not_unsold():
    ids = _make_scenario(status="Active")
    try:
        token = create_access_token(ids["seller_id"])
        resp = client.post(
            f"/auctions/{ids['auction_id']}/relist",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 400
        assert "only unsold auctions" in resp.json()["detail"].lower()
    finally:
        _cleanup(ids)


def test_relist_returns_404_for_unknown_auction():
    user_id = _make_lone_user()
    try:
        token = create_access_token(user_id)
        resp = client.post(
            f"/auctions/{uuid.uuid4()}/relist",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404
    finally:
        _cleanup_lone_user(user_id)


# --------------------------------------------------------------------- #
# buy-it-now
# --------------------------------------------------------------------- #

def test_buy_it_now_closes_auction_and_charges_buyer():
    ids = _make_scenario(buy_it_now_price=Decimal("200.00"), with_bid=False)
    try:
        token = create_access_token(ids["other_user_id"])  # acting as the buyer
        resp = client.post(
            f"/auctions/{ids['auction_id']}/buy-it-now",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "Closed"
        assert Decimal(body["current_price"]) == Decimal("200.00")

        buyer_wallet = _wallet(ids["other_user_id"])
        assert buyer_wallet.held_amount == Decimal("200.00")
    finally:
        _cleanup(ids)


def test_buy_it_now_outbids_existing_active_bid():
    ids = _make_scenario(buy_it_now_price=Decimal("200.00"), with_bid=True)
    try:
        token = create_access_token(ids["other_user_id"])
        resp = client.post(
            f"/auctions/{ids['auction_id']}/buy-it-now",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200

        previous_bidder_wallet = _wallet(ids["bidder_id"])
        assert previous_bidder_wallet.held_amount == Decimal("0.00")  # released

        db = SessionLocal()
        outbid_notification = (
            db.query(Notification)
            .filter(
                Notification.user_id == ids["bidder_id"],
                Notification.auction_id == ids["auction_id"],
                Notification.type == "outbid",
            )
            .count()
        )
        db.close()
        assert outbid_notification == 1
    finally:
        _cleanup(ids)


def test_buy_it_now_rejected_when_not_offered():
    ids = _make_scenario(buy_it_now_price=None)
    try:
        token = create_access_token(ids["other_user_id"])
        resp = client.post(
            f"/auctions/{ids['auction_id']}/buy-it-now",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 400
        assert "does not offer buy it now" in resp.json()["detail"].lower()
    finally:
        _cleanup(ids)


def test_buy_it_now_rejected_for_insufficient_funds():
    ids = _make_scenario(buy_it_now_price=Decimal("200.00"))
    try:
        # Give the buyer a wallet balance too low to cover the BIN price.
        db = SessionLocal()
        buyer_wallet = db.query(Wallet).filter(Wallet.user_id == ids["other_user_id"]).first()
        buyer_wallet.balance = Decimal("10.00")
        db.commit()
        db.close()

        token = create_access_token(ids["other_user_id"])
        resp = client.post(
            f"/auctions/{ids['auction_id']}/buy-it-now",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 400
        assert "insufficient funds" in resp.json()["detail"].lower()
    finally:
        _cleanup(ids)


def test_buy_it_now_returns_404_for_unknown_auction():
    user_id = _make_lone_user()
    try:
        token = create_access_token(user_id)
        resp = client.post(
            f"/auctions/{uuid.uuid4()}/buy-it-now",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404
    finally:
        _cleanup_lone_user(user_id)
