"""
Debug-only endpoints for constructing exact test scenarios that would
otherwise require waiting real minutes/days, or that can't occur naturally
through the normal API (e.g. two bids with an identical timestamp).

CRITICAL: every route here is gated by core.config.DEBUG_MODE. If
AUCTIONEDGE_DEBUG is not set to "true" in the environment, every endpoint
in this router returns 404 — as if it doesn't exist at all. Never enable
this in anything resembling a real deployment; it lets any authenticated
user manipulate auction timing and inject arbitrary bid state.
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.deps import get_current_user
from app.models.auction import Auction
from app.models.bid import Bid
from app.models.user import User
from app.core.config import DEBUG_MODE
from app.core.bidding import resolve_tie

router = APIRouter(prefix="/debug", tags=["debug"])


def _require_debug_mode():
    if not DEBUG_MODE:
        raise HTTPException(status_code=404, detail="Not found")


class SetEndTimeRequest(BaseModel):
    end_time: datetime


@router.patch("/auctions/{auction_id}/end-time")
def debug_set_end_time(
    auction_id: uuid.UUID,
    body: SetEndTimeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _gate=Depends(_require_debug_mode),
):
    """
    Forces an auction's end_time to an arbitrary value. Use this to
    construct exact boundary scenarios without waiting real time, e.g.:
      - Set end_time to 2 minutes from now, then place a bid, to test
        the soft-close window (<=3 min remaining) trigger precisely.
      - Set end_time to 1 second in the past, then let the next
        auto-close scheduler tick (or call debug/run-auto-close below)
        to test UC5 closure deterministically.
    """
    auction = db.get(Auction, auction_id)
    if auction is None:
        raise HTTPException(status_code=404, detail="Auction not found")

    auction.end_time = body.end_time
    db.commit()
    db.refresh(auction)
    return {"id": str(auction.id), "end_time": auction.end_time.isoformat()}


@router.post("/auctions/run-auto-close")
async def debug_run_auto_close(
    current_user: User = Depends(get_current_user),
    _gate=Depends(_require_debug_mode),
):
    """
    Manually triggers one auto-close sweep immediately, instead of waiting
    for the scheduler's next 10-second tick. Useful for deterministic tests
    that just forced an end_time into the past via the endpoint above.
    """
    from app.core.auto_close import close_expired_auctions  # local import avoids circular import at module load

    await close_expired_auctions()
    return {"status": "auto-close sweep completed"}


class InjectTiedBidsRequest(BaseModel):
    bidder_id_a: uuid.UUID
    bidder_id_b: uuid.UUID
    amount: float


@router.post("/auctions/{auction_id}/inject-tied-bids")
def debug_inject_tied_bids(
    auction_id: uuid.UUID,
    body: InjectTiedBidsRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _gate=Depends(_require_debug_mode),
):
    """
    Directly inserts two bids at the exact same amount with an IDENTICAL
    timestamp — a scenario the real place_bid endpoint can never produce
    (server-generated timestamps always differ, even at microsecond
    precision). This is the only way to actually construct the "true
    simultaneous arrival" case named in your spec (extension 6b) and in
    RQ1 ("multiple users submit bids simultaneously at the auction's
    closing moment").

    Bypasses validate_bid entirely on purpose — this is test scaffolding,
    not a real bid submission path.
    """
    auction = db.get(Auction, auction_id)
    if auction is None:
        raise HTTPException(status_code=404, detail="Auction not found")

    identical_timestamp = datetime.now(timezone.utc)

    bid_a = Bid(
        auction_id=auction_id,
        bidder_id=body.bidder_id_a,
        amount=body.amount,
        timestamp=identical_timestamp,
        status="active",
    )
    bid_b = Bid(
        auction_id=auction_id,
        bidder_id=body.bidder_id_b,
        amount=body.amount,
        timestamp=identical_timestamp,
        status="active",
    )
    db.add(bid_a)
    db.add(bid_b)
    db.commit()
    db.refresh(bid_a)
    db.refresh(bid_b)

    return {
        "bid_a_id": str(bid_a.id),
        "bid_b_id": str(bid_b.id),
        "shared_timestamp": identical_timestamp.isoformat(),
        "note": "Both bids are now 'active' simultaneously — call "
                "/debug/auctions/{auction_id}/resolve-tie to apply resolve_tie().",
    }


@router.post("/auctions/{auction_id}/resolve-tie")
def debug_resolve_tie(
    auction_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _gate=Depends(_require_debug_mode),
):
    """
    Finds all bids sharing the auction's exact highest timestamp among
    active bids (a true tie, as injected above) and applies resolve_tie()
    from core/bidding.py to deterministically pick one winner, marking
    the rest as "outbid". This is what you'd unit-test directly (call
    resolve_tie() with a list of IDs) AND integration-test end-to-end
    (inject -> resolve -> assert exactly one remains active) using this
    pair of endpoints.
    """
    active_bids = (
        db.query(Bid)
        .filter(Bid.auction_id == auction_id, Bid.status == "active")
        .all()
    )
    if not active_bids:
        raise HTTPException(status_code=400, detail="No active bids on this auction.")

    max_timestamp = max(b.timestamp for b in active_bids)
    tied = [b for b in active_bids if b.timestamp == max_timestamp]

    if len(tied) < 2:
        return {"note": "No tie found — only one bid at the max timestamp.", "winner_id": str(tied[0].id)}

    tied_ids = [b.id for b in tied]
    winner_id = resolve_tie(tied_ids)

    for b in tied:
        if b.id != winner_id:
            b.status = "outbid"

    db.commit()

    return {
        "tied_bid_ids": [str(i) for i in tied_ids],
        "winner_id": str(winner_id),
    }
