"""
Integration test for WebSocket broadcast on bid placement (plan section
3.2): a client connected to /ws/auctions/{id} must receive the
"bid_placed" event pushed by ws_manager.manager.broadcast() when someone
bids on that auction.

FastAPI's TestClient runs the ASGI app in a background thread with a real
event loop, so a websocket connection stays open and live while a normal
HTTP request is made from the same test -- this is the standard pattern
for testing broadcast-on-action behavior without a separate server process.
"""

from app.core.auth import create_access_token

from tests.integration.conftest import client


def test_websocket_receives_broadcast_on_bid_placement(bid_scenario):
    token = create_access_token(bid_scenario["bidder_1_id"])
    auction_id = bid_scenario["auction_id"]

    with client.websocket_connect(f"/ws/auctions/{auction_id}") as ws:
        resp = client.post(
            f"/auctions/{auction_id}/bids",
            json={"amount": "55.00"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 201

        message = ws.receive_json()
        assert message["event"] == "bid_placed"
        assert message["id"] == str(auction_id)
        assert message["current_price"] == "55.00"
        assert message["status"] == "Active"


def test_websocket_not_notified_for_a_different_auction(bid_scenario):
    """The manager scopes broadcasts per auction_id -- a client watching a
    DIFFERENT auction must not receive this bid's event.

    receive_json() blocks until a message arrives, so there's no clean way
    to assert "nothing was ever sent" without risking a hung test. Instead:
    connect to the OTHER auction, place a bid on the first auction (which
    must NOT be delivered here), then place a bid on the auction this
    socket actually watches -- if the first bid had leaked through, this
    receive would return ITS data instead of the second bid's."""
    token_1 = create_access_token(bid_scenario["bidder_1_id"])
    token_2 = create_access_token(bid_scenario["bidder_2_id"])
    auction_id = bid_scenario["auction_id"]
    other_auction_id = bid_scenario["other_auction_id"]

    with client.websocket_connect(f"/ws/auctions/{other_auction_id}") as ws:
        resp_unrelated = client.post(
            f"/auctions/{auction_id}/bids",
            json={"amount": "55.00"},
            headers={"Authorization": f"Bearer {token_1}"},
        )
        assert resp_unrelated.status_code == 201

        resp_watched = client.post(
            f"/auctions/{other_auction_id}/bids",
            json={"amount": "55.00"},
            headers={"Authorization": f"Bearer {token_2}"},
        )
        assert resp_watched.status_code == 201

        message = ws.receive_json()
        assert message["id"] == str(other_auction_id)  # not the unrelated auction's id
