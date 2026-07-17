"""
Fixtures for the concurrency / race-condition tier (plan section 3.4).

IMPORTANT DESIGN NOTE — why these tests don't go through the HTTP API:

place_bid() in api/bids.py is declared `async def`, but every DB call inside
it (db.query(...), db.commit(), the wallet-lock calls) is a plain
*synchronous* SQLAlchemy call, not awaited. FastAPI only offloads a request
onto a worker thread when the whole path function is defined with a plain
`def`; an `async def` endpoint's body runs directly on the single event
loop, so its blocking DB calls block that loop for their full duration.
The Dockerfile also starts uvicorn with no --workers flag (a single
process, one event loop).

The consequence: firing concurrent requests at place_bid through the ASGI
app or over real HTTP (in-process or via asyncio.gather) would NOT produce
genuinely overlapping database transactions — Python would run each
request's synchronous critical section to completion before starting the
next one, so the row-lock vs. serializable distinction this tier exists to
test would never actually be exercised. (This is worth a line in the
report: as shipped, correctness under real load depends on running uvicorn
with multiple worker processes, not on a single worker's request handling.)

To get genuine overlapping transactions, these tests instead use a
ThreadPoolExecutor: real OS threads, each opening its own DB session and
calling the exact same functions place_bid calls internally
(_fetch_auction_for_update, validate_bid, lock_wallets_in_order, etc.).
psycopg2 releases the GIL during its blocking network I/O, so separate
threads genuinely overlap at the Postgres connection level — which is
where the thing under test (SELECT ... FOR UPDATE vs. SERIALIZABLE) lives.
"""

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.models.user import User
from app.models.wallet import Wallet
from app.models.item import Item
from app.models.auction import Auction
from app.models.bid import Bid
from app.models.notification import Notification
from app.models.audit_log import AuditLogEntry
from app.core.auth import hash_password


def _make_user_with_wallet(db: Session, balance: Decimal) -> User:
    user = User(
        first_name="Concurrency", last_name="Test",
        email=f"{uuid.uuid4()}@example.test",
        password_hash=hash_password("x"),
    )
    db.add(user)
    db.flush()
    db.add(Wallet(user_id=user.id, balance=balance, held_amount=Decimal("0.00")))
    return user


def create_single_auction_scenario(num_bidders: int, balance_each: Decimal, current_price: Decimal):
    """One auction, one seller, N fresh bidders each with their own wallet."""
    db = SessionLocal()
    seller = _make_user_with_wallet(db, Decimal("0"))
    bidders = [_make_user_with_wallet(db, balance_each) for _ in range(num_bidders)]
    db.flush()

    item = Item(title="Concurrency Test Item", description="d", category="Gaming", seller_id=seller.id)
    db.add(item)
    db.flush()

    now = datetime.now(timezone.utc)
    auction = Auction(
        item_id=item.id,
        starting_price=current_price,
        reserve_price=None,
        current_price=current_price,
        start_time=now - timedelta(days=1),
        end_time=now + timedelta(hours=1),  # far from soft-close, isolates this from that mechanism
        status="Active",
    )
    db.add(auction)
    db.flush()

    ids = dict(
        auction_id=auction.id,
        item_id=item.id,
        seller_id=seller.id,
        bidder_ids=[b.id for b in bidders],
    )
    db.commit()
    db.close()
    return ids


def create_two_auction_shared_bidder_scenario(balance: Decimal, current_price_each: Decimal):
    """One bidder with a single wallet, two independent auctions/sellers —
    for the 'combined bid amount exceeds balance' double-spend scenario."""
    db = SessionLocal()
    bidder = _make_user_with_wallet(db, balance)
    seller_1 = _make_user_with_wallet(db, Decimal("0"))
    seller_2 = _make_user_with_wallet(db, Decimal("0"))
    db.flush()

    now = datetime.now(timezone.utc)

    item_1 = Item(title="Auction A Item", description="d", category="Gaming", seller_id=seller_1.id)
    item_2 = Item(title="Auction B Item", description="d", category="Gaming", seller_id=seller_2.id)
    db.add_all([item_1, item_2])
    db.flush()

    auction_1 = Auction(
        item_id=item_1.id, starting_price=current_price_each, reserve_price=None,
        current_price=current_price_each, start_time=now - timedelta(days=1),
        end_time=now + timedelta(hours=1), status="Active",
    )
    auction_2 = Auction(
        item_id=item_2.id, starting_price=current_price_each, reserve_price=None,
        current_price=current_price_each, start_time=now - timedelta(days=1),
        end_time=now + timedelta(hours=1), status="Active",
    )
    db.add_all([auction_1, auction_2])
    db.flush()

    ids = dict(
        bidder_id=bidder.id,
        seller_ids=[seller_1.id, seller_2.id],
        item_ids=[item_1.id, item_2.id],
        auction_ids=[auction_1.id, auction_2.id],
    )
    db.commit()
    db.close()
    return ids


def cleanup_scenario(*, auction_ids=(), item_ids=(), user_ids=()):
    db = SessionLocal()
    if auction_ids:
        db.query(Notification).filter(Notification.auction_id.in_(auction_ids)).delete(synchronize_session=False)
        db.query(AuditLogEntry).filter(AuditLogEntry.entity_id.in_(auction_ids)).delete(synchronize_session=False)
        db.query(Bid).filter(Bid.auction_id.in_(auction_ids)).delete(synchronize_session=False)
        db.query(Auction).filter(Auction.id.in_(auction_ids)).delete(synchronize_session=False)
    if item_ids:
        db.query(Item).filter(Item.id.in_(item_ids)).delete(synchronize_session=False)
    if user_ids:
        db.query(Wallet).filter(Wallet.user_id.in_(user_ids)).delete(synchronize_session=False)
        db.query(User).filter(User.id.in_(user_ids)).delete(synchronize_session=False)
    db.commit()
    db.close()
