"""
Integration test for the UC1 bid-placement chain (plan section 3.2):

    Bid placement -> wallet hold -> notification chain
    (api/bids.py -> core/wallet_db.py -> core/notifications.py)

Goes through the real HTTP endpoint (FastAPI TestClient) rather than
calling functions directly, since this tier is specifically about the
whole request pipeline wiring together correctly -- the locking mechanism
itself is what tests/concurrency covers.
"""

from decimal import Decimal

from app.db.database import SessionLocal
from app.models.wallet import Wallet
from app.models.notification import Notification
from app.core.auth import create_access_token

from tests.integration.conftest import client


def test_bid_placement_creates_wallet_hold_and_outbid_notification_chain(bid_scenario):
    token_1 = create_access_token(bid_scenario["bidder_1_id"])
    resp_1 = client.post(
        f"/auctions/{bid_scenario['auction_id']}/bids",
        json={"amount": "55.00"},
        headers={"Authorization": f"Bearer {token_1}"},
    )
    assert resp_1.status_code == 201

    db = SessionLocal()
    wallet_1 = db.query(Wallet).filter(Wallet.user_id == bid_scenario["bidder_1_id"]).first()
    assert wallet_1.held_amount == Decimal("55.00")
    db.close()

    # A second, higher bid should release bidder 1's hold, place a new
    # hold for bidder 2, and notify bidder 1 that they were outbid --
    # that chain reaction is what this test exists to check.
    token_2 = create_access_token(bid_scenario["bidder_2_id"])
    resp_2 = client.post(
        f"/auctions/{bid_scenario['auction_id']}/bids",
        json={"amount": "60.00"},
        headers={"Authorization": f"Bearer {token_2}"},
    )
    assert resp_2.status_code == 201

    db = SessionLocal()
    wallet_1_after = db.query(Wallet).filter(Wallet.user_id == bid_scenario["bidder_1_id"]).first()
    wallet_2_after = db.query(Wallet).filter(Wallet.user_id == bid_scenario["bidder_2_id"]).first()
    assert wallet_1_after.held_amount == Decimal("0.00")  # released
    assert wallet_2_after.held_amount == Decimal("60.00")

    outbid_notifications = (
        db.query(Notification)
        .filter(
            Notification.user_id == bid_scenario["bidder_1_id"],
            Notification.auction_id == bid_scenario["auction_id"],
            Notification.type == "outbid",
        )
        .count()
    )
    assert outbid_notifications == 1
    db.close()


def test_bid_rejected_by_validation_leaves_wallet_and_notifications_untouched(bid_scenario):
    """A bid below the minimum increment must be rejected before it ever
    touches the wallet-hold or notification chain."""
    token = create_access_token(bid_scenario["bidder_1_id"])
    resp = client.post(
        f"/auctions/{bid_scenario['auction_id']}/bids",
        json={"amount": "51.00"},  # min next bid on a $50 auction is $55
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400

    db = SessionLocal()
    wallet = db.query(Wallet).filter(Wallet.user_id == bid_scenario["bidder_1_id"]).first()
    assert wallet.held_amount == Decimal("0.00")
    notifications = (
        db.query(Notification).filter(Notification.auction_id == bid_scenario["auction_id"]).count()
    )
    assert notifications == 0
    db.close()
