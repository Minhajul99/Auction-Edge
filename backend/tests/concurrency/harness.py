"""
Direct-call bid harness for the concurrency tests in this folder.

Mirrors place_bid()'s transaction in api/bids.py, calling the exact same
functions it calls internally (_fetch_auction_for_update,
validate_bid, lock_wallets_in_order, ensure_can_hold, place_hold,
release_hold) so the strategy-dependent locking code under test is the
real production code, not a reimplementation of it. See conftest.py's
module docstring for why this bypasses the HTTP/ASGI layer entirely.
"""

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.exc import OperationalError

from app.db.database import SessionLocal
from app.models.auction import Auction
from app.models.bid import Bid
from app.api.bids import _fetch_auction_for_update
from app.core.bidding import validate_bid, BidRejected, compute_new_end_time
from app.core.wallet import InsufficientFunds
from app.core.wallet_db import lock_wallets_in_order, place_hold, release_hold, ensure_can_hold


def attempt_bid(auction_id, bidder_id, amount: Decimal) -> dict:
    db = SessionLocal()
    try:
        auction = _fetch_auction_for_update(db, auction_id)
        now = datetime.now(timezone.utc)

        current_highest_bid = (
            db.query(Bid)
            .filter(Bid.auction_id == auction_id, Bid.status == "active")
            .order_by(Bid.timestamp.desc())
            .first()
        )
        current_highest_bidder_id = (
            current_highest_bid.bidder_id if current_highest_bid else None
        )

        validate_bid(
            bid_amount=amount,
            current_price=auction.current_price,
            current_highest_bidder_id=current_highest_bidder_id,
            bidder_id=bidder_id,
            auction_status=auction.status,
            auction_end_time=auction.end_time,
            now=now,
        )

        wallet_user_ids = [bidder_id]
        if current_highest_bid is not None:
            wallet_user_ids.append(current_highest_bid.bidder_id)
        wallets = lock_wallets_in_order(db, wallet_user_ids)
        bidder_wallet = wallets[bidder_id]

        ensure_can_hold(bidder_wallet, amount)

        if current_highest_bid is not None:
            previous_wallet = wallets[current_highest_bid.bidder_id]
            release_hold(previous_wallet, current_highest_bid.amount)
            current_highest_bid.status = "outbid"

        place_hold(bidder_wallet, amount)

        db.add(Bid(auction_id=auction_id, bidder_id=bidder_id, amount=amount, timestamp=now, status="active"))
        auction.current_price = amount
        auction.end_time = compute_new_end_time(auction.end_time, now)

        db.commit()
        return {"amount": amount, "accepted": True, "reason": None}

    except BidRejected as e:
        db.rollback()
        return {"amount": amount, "accepted": False, "reason": f"BidRejected: {e.reason}"}
    except InsufficientFunds:
        db.rollback()
        return {"amount": amount, "accepted": False, "reason": "InsufficientFunds"}
    except OperationalError:
        db.rollback()
        return {"amount": amount, "accepted": False, "reason": "SerializationConflict"}
    finally:
        db.close()
