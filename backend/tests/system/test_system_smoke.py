"""
System Testing (Tier 3 taxonomy item, previously untested): the entire
integrated system running as it actually deploys -- real Docker
containers, real networking between backend and Postgres, real uvicorn
serving over a real socket, real frontend dev server -- exercised over
real HTTP, not FastAPI's in-process TestClient like every other test in
this suite.

Requires the full stack up first:
    docker compose up -d --build

This file is skipped automatically (not failed) if the stack isn't
running, since none of the other tests need Docker at all -- this is the
one deliberately different tier that assumes a real deployed environment,
closer to what "system testing... in a real-world environment" means per
the taxonomy than anything else in this suite.

Finding along the way: every other test in this suite creates users by
inserting a User row directly, bypassing the real /auth/register endpoint
entirely. This is the first test to go through it for real, and it
revealed that `@example.test` (used as the fake-email domain everywhere
else in this suite) is rejected by email-validator as an IANA special-use
reserved TLD -- `@example.com` is fine. Not a bug, just a gap in what the
rest of the suite could ever have caught.
"""

import uuid

import httpx
import pytest

from app.db.database import SessionLocal
from app.models.user import User
from app.models.wallet import Wallet
from app.models.item import Item
from app.models.auction import Auction
from app.models.bid import Bid
from app.models.notification import Notification
from app.models.audit_log import AuditLogEntry

BACKEND_URL = "http://localhost:8000"
FRONTEND_URL = "http://localhost:5173"


def _backend_is_up() -> bool:
    try:
        return httpx.get(f"{BACKEND_URL}/health", timeout=2).status_code == 200
    except httpx.HTTPError:
        return False


pytestmark = pytest.mark.skipif(
    not _backend_is_up(),
    reason="System test requires the full stack running: `docker compose up -d --build`",
)


@pytest.fixture
def api():
    """Function-scoped: each test gets its own client and its own tracked
    set of user IDs to clean up afterward, so tests stay independent."""
    created_user_ids = []

    with httpx.Client(base_url=BACKEND_URL, timeout=10) as client:
        client.created_user_ids = created_user_ids  # type: ignore[attr-defined]
        yield client

    if created_user_ids:
        db = SessionLocal()
        auctions = (
            db.query(Auction)
            .join(Item, Auction.item_id == Item.id)
            .filter(Item.seller_id.in_(created_user_ids))
            .all()
        )
        auction_ids = [a.id for a in auctions]
        item_ids = [a.item_id for a in auctions]
        # Notifications/audit entries reference these users and auctions
        # directly -- must go before the rows they reference (this exact
        # cleanup-order mistake was already made twice earlier in this
        # session; see tests/integration/test_api_fuzzing.py for the
        # first instance).
        if auction_ids:
            db.query(Notification).filter(Notification.auction_id.in_(auction_ids)).delete(synchronize_session=False)
        db.query(AuditLogEntry).filter(AuditLogEntry.user_id.in_(created_user_ids)).delete(synchronize_session=False)
        if auction_ids:
            db.query(Bid).filter(Bid.auction_id.in_(auction_ids)).delete(synchronize_session=False)
            db.query(Auction).filter(Auction.id.in_(auction_ids)).delete(synchronize_session=False)
        if item_ids:
            db.query(Item).filter(Item.id.in_(item_ids)).delete(synchronize_session=False)
        db.query(Bid).filter(Bid.bidder_id.in_(created_user_ids)).delete(synchronize_session=False)
        db.query(Wallet).filter(Wallet.user_id.in_(created_user_ids)).delete(synchronize_session=False)
        db.query(User).filter(User.id.in_(created_user_ids)).delete(synchronize_session=False)
        db.commit()
        db.close()


def _register(api, role_label):
    email = f"{role_label}-{uuid.uuid4()}@example.com"
    resp = api.post(
        "/auth/register",
        json={"first_name": role_label, "last_name": "SystemTest", "email": email, "password": "password123"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    api.created_user_ids.append(body["user"]["id"])
    return body["user"]["id"], body["access_token"]


def test_health_and_root_respond(api):
    assert api.get("/health").json() == {"status": "ok"}
    assert api.get("/").status_code == 200


def test_frontend_serves_the_app():
    resp = httpx.get(FRONTEND_URL, timeout=10)
    assert resp.status_code == 200
    assert "<div id=\"root\"" in resp.text or "<div id='root'" in resp.text


def test_full_bid_flow_over_real_http_and_real_docker_network(api):
    """Register -> create item -> create auction -> place bid -> verify,
    entirely through the real containerized deployment: this request
    crosses the actual Docker network from the backend container to the
    Postgres container, not a shared in-process connection."""
    _seller_id, seller_token = _register(api, "seller")
    _bidder_id, bidder_token = _register(api, "bidder")

    item_resp = api.post(
        "/auctions/items",
        json={"title": "System Test Item", "category": "Gaming", "photos": ["http://example.com/x.png"]},
        headers={"Authorization": f"Bearer {seller_token}"},
    )
    assert item_resp.status_code == 201, item_resp.text
    item_id = item_resp.json()["id"]

    auction_resp = api.post(
        "/auctions",
        json={"item_id": item_id, "starting_price": "50.00", "duration_days": 3},
        headers={"Authorization": f"Bearer {seller_token}"},
    )
    assert auction_resp.status_code == 201, auction_resp.text
    auction = auction_resp.json()
    assert auction["current_price"] == "50.00"
    auction_id = auction["id"]

    bid_resp = api.post(
        f"/auctions/{auction_id}/bids",
        json={"amount": "55.00"},
        headers={"Authorization": f"Bearer {bidder_token}"},
    )
    assert bid_resp.status_code == 201, bid_resp.text

    updated = api.get(f"/auctions/{auction_id}")
    assert updated.status_code == 200
    assert updated.json()["current_price"] == "55.00"

    mine = api.get("/auctions/bids/mine", headers={"Authorization": f"Bearer {bidder_token}"})
    assert mine.status_code == 200
    assert any(b["amount"] == "55.00" for b in mine.json())


def test_adversarial_amount_still_gets_a_clean_response_not_a_500(api):
    """Regression check, over real HTTP this time, for the NaN/Infinity
    500 found and fixed via HTTP-boundary fuzzing (tests/integration/
    test_api_fuzzing.py) -- confirms the fix holds in the actual deployed
    container, not just under TestClient."""
    _seller_id, seller_token = _register(api, "seller")
    item_resp = api.post(
        "/auctions/items",
        json={"title": "Fuzz Regression Item", "category": "Gaming", "photos": ["http://example.com/x.png"]},
        headers={"Authorization": f"Bearer {seller_token}"},
    )
    auction_resp = api.post(
        "/auctions",
        json={"item_id": item_resp.json()["id"], "starting_price": "50.00", "duration_days": 3},
        headers={"Authorization": f"Bearer {seller_token}"},
    )
    auction_id = auction_resp.json()["id"]

    resp = api.post(
        f"/auctions/{auction_id}/bids",
        content=b'{"amount": NaN}',
        headers={"Authorization": f"Bearer {seller_token}", "Content-Type": "application/json"},
    )
    assert resp.status_code == 422, resp.text
