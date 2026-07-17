import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.deps import get_current_user, get_current_admin
from app.models.item import Item
from app.models.auction import Auction
from app.models.bid import Bid
from app.models.user import User
from app.schemas.item import ItemCreate, ItemOut
from app.schemas.auction import AuctionCreate, AuctionOut
from app.core.bidding import validate_buy_it_now, BuyItNowRejected
from app.core.notifications import create_notification
from app.core.audit import log_action
from app.core.wallet import InsufficientFunds
from app.core.wallet_db import lock_wallets_in_order, place_hold, release_hold, finalize_charge, ensure_can_hold

router = APIRouter(prefix="/auctions", tags=["auctions"])


@router.post("/items", response_model=ItemOut, status_code=status.HTTP_201_CREATED)
def create_item(
    item_in: ItemCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Step 1 of UC2: create the Item record, owned by the logged-in user."""
    db_item = Item(
        title=item_in.title,
        description=item_in.description,
        category=item_in.category,
        photos=item_in.photos,
        seller_id=current_user.id,
    )
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item


@router.post("", response_model=AuctionOut, status_code=status.HTTP_201_CREATED)
def create_auction(
    auction_in: AuctionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Step 2 of UC2: create the Auction for an existing Item owned by the user."""
    item = db.get(Item, auction_in.item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    if item.seller_id != current_user.id:
        raise HTTPException(status_code=403, detail="You can only auction your own items.")

    now = datetime.now(timezone.utc)
    end_time = now + timedelta(days=auction_in.duration_days)

    db_auction = Auction(
        item_id=auction_in.item_id,
        starting_price=auction_in.starting_price,
        reserve_price=auction_in.reserve_price,
        buy_it_now_price=auction_in.buy_it_now_price,
        current_price=auction_in.starting_price,
        start_time=now,
        end_time=end_time,
        status="Active",
    )
    db.add(db_auction)
    db.commit()
    db.refresh(db_auction)

    return _to_auction_out(db_auction)


@router.post("/{auction_id}/buy-it-now", response_model=AuctionOut)
def buy_it_now(
    auction_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Instant purchase: bypasses the timer entirely. On success, the auction
    closes immediately as "Closed" (Sold), the winning "bid" is recorded at
    the buy_it_now_price, and any standard bid arriving after this is
    rejected by validate_bid's normal 3a check (auction_status != "Active").

    Row-locked the same way as place_bid, so a standard bid racing against
    a Buy It Now click at the same instant is resolved deterministically —
    whichever transaction acquires the lock first wins; the other sees the
    updated status/price and is rejected. This is a new race-condition
    variant beyond the original soft-close scenario, worth its own TLA+
    consideration if you extend the model.
    """
    auction = (
        db.query(Auction)
        .filter(Auction.id == auction_id)
        .with_for_update()
        .first()
    )
    if auction is None:
        raise HTTPException(status_code=404, detail="Auction not found")

    now = datetime.now(timezone.utc)

    try:
        validate_buy_it_now(
            buy_it_now_price=auction.buy_it_now_price,
            current_price=auction.current_price,
            auction_status=auction.status,
            auction_end_time=auction.end_time,
            now=now,
        )
    except BuyItNowRejected as e:
        raise HTTPException(status_code=400, detail=e.reason)

    # Mark any existing active bid as outbid — BIN supersedes it. Release
    # its wallet hold, then place a new hold for the BIN purchaser. Both
    # wallets are locked together, in fixed order, same discipline as
    # place_bid.
    existing_highest = (
        db.query(Bid)
        .filter(Bid.auction_id == auction_id, Bid.status == "active")
        .order_by(Bid.timestamp.desc())
        .first()
    )

    wallet_user_ids = [current_user.id]
    if existing_highest is not None:
        wallet_user_ids.append(existing_highest.bidder_id)
    wallets = lock_wallets_in_order(db, wallet_user_ids)

    buyer_wallet = wallets[current_user.id]
    try:
        ensure_can_hold(buyer_wallet, auction.buy_it_now_price)
    except InsufficientFunds as e:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient funds: {e.available} available, {e.required} required.",
        )

    if existing_highest is not None:
        release_hold(wallets[existing_highest.bidder_id], existing_highest.amount)
        existing_highest.status = "outbid"
        create_notification(
            db, user_id=existing_highest.bidder_id, auction_id=auction_id,
            notification_type="outbid",
        )

    place_hold(buyer_wallet, auction.buy_it_now_price)

    winning_bid = Bid(
        auction_id=auction_id,
        bidder_id=current_user.id,
        amount=auction.buy_it_now_price,
        timestamp=now,
        status="active",
    )
    db.add(winning_bid)
    db.flush()

    auction.current_price = auction.buy_it_now_price
    auction.status = "Closed"  # bypasses the timer/auto-close entirely

    create_notification(
        db, user_id=current_user.id, auction_id=auction_id, notification_type="won"
    )
    create_notification(
        db, user_id=auction.item.seller_id, auction_id=auction_id,
        notification_type="seller_auction_closed",
    )

    log_action(
        db,
        user_id=current_user.id,
        action="buy_it_now",
        entity_type="Auction",
        entity_id=auction_id,
    )

    db.commit()
    db.refresh(auction)

    return _to_auction_out(auction)


@router.post("/{auction_id}/relist", response_model=AuctionOut, status_code=status.HTTP_201_CREATED)
def relist_auction(
    auction_id: uuid.UUID,
    duration_days: int | None = None,
    starting_price: float | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Relisting flow: creates a fresh Auction for the same Item after one
    closed unsold. Only the seller can relist, and only if the previous
    auction actually ended unsold.
    """
    old_auction = db.get(Auction, auction_id)
    if old_auction is None:
        raise HTTPException(status_code=404, detail="Auction not found")

    item = db.get(Item, old_auction.item_id)
    if item.seller_id != current_user.id:
        raise HTTPException(status_code=403, detail="You can only relist your own items.")

    if old_auction.status not in ("Unsold-NoBids", "Unsold-ReserveNotMet"):
        raise HTTPException(
            status_code=400,
            detail="Only unsold auctions (no bids, or reserve not met) can be relisted.",
        )

    new_starting_price = (
        Decimal(str(starting_price)) if starting_price is not None else old_auction.starting_price
    )
    new_duration = duration_days if duration_days in (3, 5, 7, 10) else 7

    now = datetime.now(timezone.utc)
    new_auction = Auction(
        item_id=item.id,
        starting_price=new_starting_price,
        reserve_price=old_auction.reserve_price,
        buy_it_now_price=old_auction.buy_it_now_price,
        current_price=new_starting_price,
        start_time=now,
        end_time=now + timedelta(days=new_duration),
        status="Active",
    )
    db.add(new_auction)
    db.commit()
    db.refresh(new_auction)

    return _to_auction_out(new_auction)


@router.post("/{auction_id}/pay", response_model=AuctionOut)
def pay_for_auction(
    auction_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Payment stub — no real gateway (Stripe, etc.) integrated. Just flips
    payment_status to "paid" if the caller is the actual winning bidder
    on a Closed (Sold) auction.
    """
    auction = db.get(Auction, auction_id)
    if auction is None:
        raise HTTPException(status_code=404, detail="Auction not found")

    if auction.status != "Closed":
        raise HTTPException(status_code=400, detail="This auction has no winner to pay for yet.")

    winning_bid = (
        db.query(Bid)
        .filter(Bid.auction_id == auction_id, Bid.status == "active")
        .order_by(Bid.amount.desc())
        .first()
    )
    if winning_bid is None or winning_bid.bidder_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the winning bidder can pay for this auction.")

    if auction.payment_status == "paid":
        raise HTTPException(status_code=400, detail="This auction has already been paid for.")

    wallets = lock_wallets_in_order(db, [current_user.id])
    finalize_charge(wallets[current_user.id], winning_bid.amount)

    auction.payment_status = "paid"
    db.commit()
    db.refresh(auction)

    return _to_auction_out(auction)


@router.get("/mine", response_model=list[AuctionOut])
def list_my_auctions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Dashboard: all auctions for items owned by the logged-in seller."""
    auctions = (
        db.query(Auction)
        .join(Item, Auction.item_id == Item.id)
        .filter(Item.seller_id == current_user.id)
        .order_by(Auction.start_time.desc())
        .all()
    )
    return [_to_auction_out(a) for a in auctions]


@router.get("", response_model=list[AuctionOut])
def list_auctions(
    status_filter: str | None = None,
    category: str | None = None,
    min_price: float | None = Query(None, ge=0),
    max_price: float | None = Query(None, ge=0),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """
    Browse endpoint — public, no auth required.

    Query params:
    - status_filter: e.g. "Active"
    - category: exact match against Item.category
    - min_price / max_price: filters on Auction.current_price (rejects
      negative values at the FastAPI/Pydantic layer via Query(ge=0), before
      this function body even runs — a clean boundary for symbolic
      execution / edge-case input testing)
    - page / page_size: 1-indexed pagination; page=0 is rejected by
      Query(ge=1) the same way

    An out-of-range page (e.g. page=999 when only 2 pages exist) is not an
    error — it simply returns an empty list, per standard REST pagination
    convention. Worth a test case either way.
    """
    query = db.query(Auction).join(Item, Auction.item_id == Item.id)

    if status_filter:
        query = query.filter(Auction.status == status_filter)
    if category:
        query = query.filter(Item.category == category)
    if min_price is not None:
        query = query.filter(Auction.current_price >= min_price)
    if max_price is not None:
        query = query.filter(Auction.current_price <= max_price)

    query = query.order_by(Auction.start_time.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    auctions = query.all()
    return [_to_auction_out(a) for a in auctions]


@router.delete("/{auction_id}", status_code=status.HTTP_204_NO_CONTENT)
def admin_delete_auction(
    auction_id: uuid.UUID,
    _admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    RBAC: admin-only. A regular user hitting this (even on their own
    auction) gets 403 from get_current_admin before this body ever runs.
    Standard users have no delete endpoint at all — only admins can
    remove an auction outright; sellers can only let theirs close naturally
    or relist.
    """
    auction = db.get(Auction, auction_id)
    if auction is None:
        raise HTTPException(status_code=404, detail="Auction not found")

    db.delete(auction)
    db.commit()
    return None


@router.get("/{auction_id}", response_model=AuctionOut)
def get_auction(auction_id: uuid.UUID, db: Session = Depends(get_db)):
    auction = db.get(Auction, auction_id)
    if auction is None:
        raise HTTPException(status_code=404, detail="Auction not found")
    return _to_auction_out(auction)


def _to_auction_out(auction: Auction) -> AuctionOut:
    reserve_met = (
        auction.reserve_price is None or auction.current_price >= auction.reserve_price
    )
    photo = auction.item.photos[0] if auction.item and auction.item.photos else None
    return AuctionOut(
        id=auction.id,
        item_id=auction.item_id,
        starting_price=auction.starting_price,
        current_price=auction.current_price,
        start_time=auction.start_time,
        end_time=auction.end_time,
        status=auction.status,
        reserve_met=reserve_met,
        payment_status=auction.payment_status,
        photo=photo,
        buy_it_now_price=auction.buy_it_now_price,
    )
