import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError

from app.db.database import get_db
from app.deps import get_current_user, get_current_admin
from app.models.auction import Auction
from app.models.bid import Bid
from app.models.user import User
from app.schemas.bid import BidCreate, BidOut, BidHistoryEntry
from app.core.bidding import (
    validate_bid,
    BidRejected,
    compute_new_end_time,
    is_reserve_met,
    is_retractable,
    exceeds_active_bid_limit,
)
from app.core.notifications import create_notification
from app.core.audit import log_action
from app.core.config import LOCKING_STRATEGY
from app.core.wallet import InsufficientFunds
from app.core.wallet_db import lock_wallets_in_order, place_hold, release_hold, ensure_can_hold
from app.api.ws_manager import manager

router = APIRouter(prefix="/auctions", tags=["bids"])


def _auction_to_ws_payload(auction: Auction, event: str) -> dict:
    reserve_met = (
        auction.reserve_price is None or auction.current_price >= auction.reserve_price
    )
    return {
        "event": event,
        "id": str(auction.id),
        "current_price": str(auction.current_price),
        "end_time": auction.end_time.isoformat(),
        "status": auction.status,
        "reserve_met": reserve_met,
    }


def _fetch_auction_for_update(db: Session, auction_id: uuid.UUID):
    """
    Two concurrency-control strategies, switchable via
    AUCTIONEDGE_LOCKING_STRATEGY (see core/config.py).
    """
    if LOCKING_STRATEGY == "serializable":
        db.connection(execution_options={"isolation_level": "SERIALIZABLE"})
        return db.query(Auction).filter(Auction.id == auction_id).first()
    else:
        return (
            db.query(Auction)
            .filter(Auction.id == auction_id)
            .with_for_update()
            .first()
        )


@router.post("/{auction_id}/bids", response_model=BidOut, status_code=status.HTTP_201_CREATED)
async def place_bid(
    auction_id: uuid.UUID,
    bid_in: BidCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    UC1: Place Bid.

    Now also enforces the wallet hold invariant (held_amount <= balance,
    always). Two wallets may need locking in this transaction — the new
    bidder's, and the previous highest bidder's (whose hold gets released)
    — see core/wallet_db.lock_wallets_in_order for why they're always
    locked in a fixed, sorted order (deadlock avoidance).
    """
    bidder_id = current_user.id
    client_ip = request.client.host if request.client else None

    auction = _fetch_auction_for_update(db, auction_id)
    if auction is None:
        raise HTTPException(status_code=404, detail="Auction not found")

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

    already_leading_here = current_highest_bidder_id == bidder_id
    if not already_leading_here:
        active_bid_count = (
            db.query(Bid)
            .filter(Bid.bidder_id == bidder_id, Bid.status == "active")
            .count()
        )
        if exceeds_active_bid_limit(active_bid_count):
            raise HTTPException(
                status_code=400,
                detail=(
                    "You already have the maximum number of active bids "
                    "(5). Wait for one to be outbid, won, or retract one "
                    "before placing a new bid."
                ),
            )

    try:
        validate_bid(
            bid_amount=bid_in.amount,
            current_price=auction.current_price,
            current_highest_bidder_id=current_highest_bidder_id,
            bidder_id=bidder_id,
            auction_status=auction.status,
            auction_end_time=auction.end_time,
            now=now,
        )
    except BidRejected as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=e.reason)

    # --- Wallet hold: lock every wallet this transaction touches, in a
    # fixed order, BEFORE mutating any of them.
    wallet_user_ids = [bidder_id]
    if current_highest_bid is not None:
        wallet_user_ids.append(current_highest_bid.bidder_id)
    wallets = lock_wallets_in_order(db, wallet_user_ids)

    bidder_wallet = wallets[bidder_id]
    try:
        ensure_can_hold(bidder_wallet, bid_in.amount)
    except InsufficientFunds as e:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient funds: {e.available} available, {e.required} required.",
        )

    if current_highest_bid is not None:
        previous_wallet = wallets[current_highest_bid.bidder_id]
        release_hold(previous_wallet, current_highest_bid.amount)
        current_highest_bid.status = "outbid"
        create_notification(
            db,
            user_id=current_highest_bid.bidder_id,
            auction_id=auction_id,
            notification_type="outbid",
        )

    place_hold(bidder_wallet, bid_in.amount)

    new_bid = Bid(
        auction_id=auction_id,
        bidder_id=bidder_id,
        amount=bid_in.amount,
        timestamp=now,
        status="active",
    )
    db.add(new_bid)
    db.flush()

    reserve_was_met_before = is_reserve_met(auction.reserve_price, auction.current_price)
    auction.current_price = bid_in.amount
    auction.end_time = compute_new_end_time(auction.end_time, now)

    reserve_met_now = is_reserve_met(auction.reserve_price, auction.current_price)
    if reserve_met_now and not reserve_was_met_before:
        create_notification(
            db,
            user_id=auction.item.seller_id,
            auction_id=auction_id,
            notification_type="reserve_met",
        )

    log_action(
        db,
        user_id=bidder_id,
        action="bid_placed",
        entity_type="Bid",
        entity_id=new_bid.id,
        ip_address=client_ip,
    )

    try:
        db.commit()
    except OperationalError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="This bid conflicted with another concurrent bid. Please try again.",
        )

    db.refresh(new_bid)
    db.refresh(auction)

    await manager.broadcast(auction_id, _auction_to_ws_payload(auction, "bid_placed"))

    return new_bid


@router.post("/{auction_id}/bids/{bid_id}/retract", response_model=BidOut)
async def retract_bid(
    auction_id: uuid.UUID,
    bid_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """UC3: Retract Bid. Releases the wallet hold on success."""
    bidder_id = current_user.id
    client_ip = request.client.host if request.client else None

    auction = (
        db.query(Auction)
        .filter(Auction.id == auction_id)
        .with_for_update()
        .first()
    )
    if auction is None:
        raise HTTPException(status_code=404, detail="Auction not found")

    if auction.status != "Active":
        raise HTTPException(status_code=400, detail="Closed auctions cannot be modified.")

    bid = db.get(Bid, bid_id)
    if bid is None or bid.auction_id != auction_id:
        raise HTTPException(status_code=404, detail="Bid not found")

    if bid.bidder_id != bidder_id:
        raise HTTPException(status_code=403, detail="You can only retract your own bid.")

    if bid.status != "active":
        raise HTTPException(
            status_code=400,
            detail="This bid can no longer be retracted (already withdrawn or outbid).",
        )

    now = datetime.now(timezone.utc)

    if not is_retractable(bid.timestamp, now):
        raise HTTPException(
            status_code=400,
            detail="This bid can no longer be retracted — the 15-minute window has passed.",
        )

    was_leading_bid = bid.status == "active" and (
        db.query(Bid)
        .filter(Bid.auction_id == auction_id, Bid.status == "active")
        .order_by(Bid.timestamp.desc())
        .first().id
        == bid.id
    )

    wallets = lock_wallets_in_order(db, [bidder_id])
    release_hold(wallets[bidder_id], bid.amount)

    bid.status = "withdrawn"
    price_changed = False

    if was_leading_bid:
        next_highest = (
            db.query(Bid)
            .filter(Bid.auction_id == auction_id, Bid.status == "active")
            .order_by(Bid.amount.desc())
            .first()
        )
        auction.current_price = next_highest.amount if next_highest else auction.starting_price
        price_changed = True

    log_action(
        db,
        user_id=bidder_id,
        action="bid_retracted",
        entity_type="Bid",
        entity_id=bid.id,
        ip_address=client_ip,
    )

    db.commit()
    db.refresh(bid)

    if price_changed:
        db.refresh(auction)
        await manager.broadcast(auction_id, _auction_to_ws_payload(auction, "bid_retracted"))

    return bid


@router.post("/{auction_id}/bids/{bid_id}/admin-cancel", response_model=BidOut)
def admin_cancel_bid(
    auction_id: uuid.UUID,
    bid_id: uuid.UUID,
    _admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """RBAC: admin-only equivalent of retract_bid. Also releases the wallet hold."""
    auction = db.query(Auction).filter(Auction.id == auction_id).with_for_update().first()
    if auction is None:
        raise HTTPException(status_code=404, detail="Auction not found")

    bid = db.get(Bid, bid_id)
    if bid is None or bid.auction_id != auction_id:
        raise HTTPException(status_code=404, detail="Bid not found")

    if bid.status != "active":
        raise HTTPException(status_code=400, detail="This bid is not currently active.")

    was_leading_bid = (
        db.query(Bid)
        .filter(Bid.auction_id == auction_id, Bid.status == "active")
        .order_by(Bid.timestamp.desc())
        .first().id
        == bid.id
    )

    wallets = lock_wallets_in_order(db, [bid.bidder_id])
    release_hold(wallets[bid.bidder_id], bid.amount)

    bid.status = "withdrawn"

    if was_leading_bid:
        next_highest = (
            db.query(Bid)
            .filter(Bid.auction_id == auction_id, Bid.status == "active")
            .order_by(Bid.amount.desc())
            .first()
        )
        auction.current_price = next_highest.amount if next_highest else auction.starting_price

    log_action(
        db,
        user_id=_admin.id,
        action="admin_cancelled_bid",
        entity_type="Bid",
        entity_id=bid.id,
    )

    db.commit()
    db.refresh(bid)
    return bid


@router.get("/bids/mine", response_model=list[BidOut])
def list_my_bids(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    bids = (
        db.query(Bid)
        .filter(Bid.bidder_id == current_user.id)
        .order_by(Bid.timestamp.desc())
        .all()
    )
    return bids


@router.get("/{auction_id}/bids/history", response_model=list[BidHistoryEntry])
def get_bid_history(auction_id: uuid.UUID, db: Session = Depends(get_db)):
    auction = db.get(Auction, auction_id)
    if auction is None:
        raise HTTPException(status_code=404, detail="Auction not found")

    bids = (
        db.query(Bid)
        .filter(Bid.auction_id == auction_id, Bid.status != "withdrawn")
        .order_by(Bid.timestamp.desc())
        .all()
    )

    bids_chronological = sorted(bids, key=lambda b: b.timestamp)
    label_map: dict[uuid.UUID, str] = {}
    next_label_num = 1
    for b in bids_chronological:
        if b.bidder_id not in label_map:
            label_map[b.bidder_id] = f"Bidder #{next_label_num}"
            next_label_num += 1

    return [
        BidHistoryEntry(
            amount=b.amount,
            timestamp=b.timestamp,
            masked_bidder=label_map[b.bidder_id],
        )
        for b in bids
    ]
