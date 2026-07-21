"""
UC5: Auction Auto-Close (System-Triggered).

Runs periodically via APScheduler's AsyncIOScheduler (wired in main.py),
so it can await WebSocket broadcasts on the same event loop as the rest
of the app.
"""

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.models.auction import Auction
from app.models.bid import Bid
from app.core.bidding import determine_close_outcome
from app.core.notifications import create_notification
from app.core.audit import log_action
from app.core.wallet_db import lock_wallets_in_order, release_hold
from app.api.ws_manager import manager

logger = logging.getLogger("auction_edge.auto_close")


async def close_expired_auctions() -> None:
    """
    Finds all Active auctions whose end_time has passed and closes them.

    Idempotent: only auctions still in "Active" status are touched, so a
    second/overlapping run (e.g. from scheduler retries) has no effect on
    auctions already closed by a prior run.

    Atomicity: each auction is locked with SELECT ... FOR UPDATE before
    closing, so a bid that arrives concurrently (and would trigger a
    soft-close extension) is serialized against this check rather than
    racing it — the core concurrency invariant for UC5.
    """
    db: Session = SessionLocal()
    try:
        now = datetime.now(timezone.utc)

        expired_auction_ids = (
            db.query(Auction.id)
            .filter(Auction.status == "Active", Auction.end_time <= now)
            .all()
        )

        for (auction_id,) in expired_auction_ids:
            await _close_single_auction(db, auction_id, now)

    finally:
        db.close()


def close_auction_as_sold(db: Session, auction: Auction, winning_bid: Bid) -> None:
    """
    Shared "Sold" closure logic: sets status and fires the winner/seller/
    losers notification fan-out. Reused by the scheduler-driven auto-close
    sweep below and by the seller's manual "accept bid early" endpoint
    (api/auctions.py) — same outcome, two different triggers.

    Does NOT commit, log the audit action, or broadcast -- callers differ
    on timing/action-name/acting-user for those, so they stay caller-side.
    """
    auction.status = "Closed"

    create_notification(
        db, user_id=winning_bid.bidder_id, auction_id=auction.id, notification_type="won"
    )
    create_notification(
        db, user_id=auction.item.seller_id, auction_id=auction.id,
        notification_type="seller_auction_closed",
    )
    other_bidder_ids = {
        b.bidder_id
        for b in db.query(Bid)
        .filter(Bid.auction_id == auction.id, Bid.status.in_(["active", "outbid"]))
        .all()
        if b.bidder_id != winning_bid.bidder_id
    }
    for bidder_id in other_bidder_ids:
        create_notification(
            db, user_id=bidder_id, auction_id=auction.id, notification_type="lost"
        )


async def _close_single_auction(db: Session, auction_id: uuid.UUID, now: datetime) -> None:
    # Row-level lock — if a bid is mid-flight on this auction (extending
    # end_time via soft-close), this blocks until that transaction commits,
    # then re-checks status/end_time below before closing.
    auction = (
        db.query(Auction)
        .filter(Auction.id == auction_id)
        .with_for_update()
        .first()
    )

    if auction is None:
        return

    # Re-check after acquiring the lock: another process may have already
    # closed it, or a concurrent bid may have pushed end_time forward
    # (soft-close), in which case it's no longer actually expired.
    if auction.status != "Active" or auction.end_time > now:
        return

    highest_bid = (
        db.query(Bid)
        .filter(Bid.auction_id == auction_id, Bid.status == "active")
        .order_by(Bid.amount.desc())
        .first()
    )

    outcome = determine_close_outcome(
        has_bids=highest_bid is not None,
        reserve_price=auction.reserve_price,
        current_price=auction.current_price,
    )

    if outcome == "Sold":
        close_auction_as_sold(db, auction, highest_bid)
        logger.info(f"Auction {auction_id} closed — SOLD at {auction.current_price}")

    elif outcome == "Unsold-NoBids":
        auction.status = "Unsold-NoBids"
        create_notification(
            db, user_id=auction.item.seller_id, auction_id=auction_id,
            notification_type="unsold_no_bids",
        )
        logger.info(f"Auction {auction_id} closed — no bids placed")

    else:  # Unsold-ReserveNotMet
        auction.status = "Unsold-ReserveNotMet"

        # No sale occurred, so the leading bid's held funds must be
        # returned — otherwise this user's money stays frozen forever
        # with nothing to ever finalize it. The bid record itself stays
        # "active" (it genuinely was the leading bid, for audit/history
        # purposes) — only the wallet hold is released.
        if highest_bid is not None:
            wallets = lock_wallets_in_order(db, [highest_bid.bidder_id])
            release_hold(wallets[highest_bid.bidder_id], highest_bid.amount)

        create_notification(
            db, user_id=auction.item.seller_id, auction_id=auction_id,
            notification_type="unsold_reserve_not_met",
        )
        logger.info(f"Auction {auction_id} closed — reserve not met")

    log_action(
        db,
        user_id=None,  # system-triggered, no specific acting user
        action="auction_closed",
        entity_type="Auction",
        entity_id=auction_id,
    )

    db.commit()
    db.refresh(auction)

    reserve_met = (
        auction.reserve_price is None or auction.current_price >= auction.reserve_price
    )
    await manager.broadcast(auction_id, {
        "event": "auction_closed",
        "id": str(auction.id),
        "current_price": str(auction.current_price),
        "end_time": auction.end_time.isoformat(),
        "status": auction.status,
        "reserve_met": reserve_met,
    })
