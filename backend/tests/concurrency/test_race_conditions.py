"""
Concurrency / race-condition tests (plan section 3.4, RQ1 + RQ4).

See conftest.py's module docstring for why these use a ThreadPoolExecutor
of real DB sessions instead of concurrent HTTP requests.
"""

from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

import pytest

from app.db.database import SessionLocal
from app.models.auction import Auction
from app.models.bid import Bid
from app.models.wallet import Wallet
from app.models.user import User
from app.api.debug import (
    debug_inject_tied_bids,
    debug_resolve_tie,
    InjectTiedBidsRequest,
)

from tests.concurrency.conftest import (
    create_single_auction_scenario,
    create_two_auction_shared_bidder_scenario,
    cleanup_scenario,
)
from tests.concurrency.harness import attempt_bid


def test_concurrent_bids_on_one_auction_no_lost_updates(monkeypatch):
    """N bidders submit closely-spaced escalating amounts at the same
    moment. Under correct row-locking, exactly one can win — the others
    fail the minimum-increment check once the winner's price is applied.
    If more than one succeeded, that's a lost-update race condition."""
    monkeypatch.setattr("app.api.bids.LOCKING_STRATEGY", "row_lock")

    ids = create_single_auction_scenario(
        num_bidders=5, balance_each=Decimal("1000.00"), current_price=Decimal("50.00")
    )
    amounts = [Decimal(a) for a in (55, 56, 57, 58, 59)]

    try:
        with ThreadPoolExecutor(max_workers=5) as ex:
            futures = [
                ex.submit(attempt_bid, ids["auction_id"], bidder_id, amount)
                for bidder_id, amount in zip(ids["bidder_ids"], amounts)
            ]
            results = [f.result() for f in futures]

        accepted = [r for r in results if r["accepted"]]
        assert len(accepted) == 1, f"expected exactly one accepted bid, got {results}"

        db = SessionLocal()
        auction = db.get(Auction, ids["auction_id"])
        assert auction.current_price == accepted[0]["amount"]

        active_bids = (
            db.query(Bid)
            .filter(Bid.auction_id == ids["auction_id"], Bid.status == "active")
            .count()
        )
        assert active_bids == 1
        db.close()
    finally:
        cleanup_scenario(
            auction_ids=[ids["auction_id"]], item_ids=[ids["item_id"]],
            user_ids=[ids["seller_id"], *ids["bidder_ids"]],
        )


def test_concurrent_bids_across_two_auctions_shared_wallet_enforces_single_success(monkeypatch):
    """Same user, two different auctions, each requiring a $100 bid to win
    — but the wallet only has $100 total. Both bids arrive at the same
    moment; the wallet-hold invariant (held <= balance) must allow exactly
    one to succeed, not both (the double-spend guard, under real
    concurrent access rather than the sequential check in
    tests/integration/test_wallet_invariant.py)."""
    monkeypatch.setattr("app.api.bids.LOCKING_STRATEGY", "row_lock")

    ids = create_two_auction_shared_bidder_scenario(
        balance=Decimal("100.00"), current_price_each=Decimal("95.00")
    )
    bid_amount = Decimal("100.00")  # minimum_next_bid(95) == 100

    try:
        with ThreadPoolExecutor(max_workers=2) as ex:
            f1 = ex.submit(attempt_bid, ids["auction_ids"][0], ids["bidder_id"], bid_amount)
            f2 = ex.submit(attempt_bid, ids["auction_ids"][1], ids["bidder_id"], bid_amount)
            r1, r2 = f1.result(), f2.result()

        accepted = [r for r in (r1, r2) if r["accepted"]]
        assert len(accepted) == 1, f"expected exactly one accepted bid, got {[r1, r2]}"

        db = SessionLocal()
        wallet = db.query(Wallet).filter(Wallet.user_id == ids["bidder_id"]).first()
        assert wallet.held_amount == Decimal("100.00")  # not 200 -- no double-spend
        assert wallet.held_amount <= wallet.balance
        db.close()
    finally:
        cleanup_scenario(
            auction_ids=ids["auction_ids"], item_ids=ids["item_ids"],
            user_ids=[ids["bidder_id"], *ids["seller_ids"]],
        )


def test_tied_bid_injection_and_resolution():
    """RQ1's true-simultaneous-arrival case: two bids at an identical
    timestamp (only possible via the debug injection endpoint — the real
    place_bid path can never produce this). resolve_tie() must leave
    exactly one bid active."""
    ids = create_single_auction_scenario(
        num_bidders=2, balance_each=Decimal("1000.00"), current_price=Decimal("50.00")
    )
    auction_id = ids["auction_id"]
    bidder_a_id, bidder_b_id = ids["bidder_ids"]

    try:
        db = SessionLocal()
        acting_user = db.get(User, bidder_a_id)

        inject_result = debug_inject_tied_bids(
            auction_id,
            InjectTiedBidsRequest(bidder_id_a=bidder_a_id, bidder_id_b=bidder_b_id, amount=60.0),
            current_user=acting_user,
            db=db,
            _gate=None,
        )

        active_before = (
            db.query(Bid).filter(Bid.auction_id == auction_id, Bid.status == "active").count()
        )
        assert active_before == 2  # the genuine tie the endpoint claims to construct

        resolve_result = debug_resolve_tie(auction_id, current_user=acting_user, db=db, _gate=None)

        active_after = (
            db.query(Bid).filter(Bid.auction_id == auction_id, Bid.status == "active").all()
        )
        assert len(active_after) == 1
        assert str(active_after[0].id) == resolve_result["winner_id"]
        # resolve_tie() only guarantees totality + determinism, not which
        # side wins (see its docstring in core/bidding.py) — so the winner
        # must be one of the two tied bids, not necessarily bid_a.
        assert resolve_result["winner_id"] in (inject_result["bid_a_id"], inject_result["bid_b_id"])
        db.close()
    finally:
        cleanup_scenario(
            auction_ids=[auction_id], item_ids=[ids["item_id"]],
            user_ids=[ids["seller_id"], *ids["bidder_ids"]],
        )


@pytest.mark.parametrize("strategy", ["row_lock", "serializable"])
def test_locking_strategy_maintains_correctness_under_contention(monkeypatch, strategy, capsys):
    """RQ4 comparative analysis: run the same contention scenario under
    both locking strategies and compare conflict/retry behavior.

    The amounts here (55..62) span more than one $5 increment tier, so
    more than one bid can legitimately win IN SEQUENCE (e.g. 55 wins, then
    a later-processed 60 legitimately outbids it) -- that's normal auction
    behavior, not a lost update. The actual correctness invariant is:
    final current_price matches the highest ACCEPTED bid, and exactly one
    bid ends up "active" (every superseded winner was correctly flipped to
    "outbid", not silently overwritten). The expected DIFFERENCE between
    strategies is mechanism, not outcome: row_lock serializes by blocking
    (0 aborted transactions), serializable serializes by aborting the
    loser of a conflicting pair (>=0 aborted transactions that a real
    client would retry)."""
    monkeypatch.setattr("app.api.bids.LOCKING_STRATEGY", strategy)

    ids = create_single_auction_scenario(
        num_bidders=8, balance_each=Decimal("1000.00"), current_price=Decimal("50.00")
    )
    amounts = [Decimal(a) for a in range(55, 63)]  # 55..62, all within one $5 increment tier

    try:
        with ThreadPoolExecutor(max_workers=8) as ex:
            futures = [
                ex.submit(attempt_bid, ids["auction_id"], bidder_id, amount)
                for bidder_id, amount in zip(ids["bidder_ids"], amounts)
            ]
            results = [f.result() for f in futures]

        accepted = [r for r in results if r["accepted"]]
        conflicts = [r for r in results if r["reason"] == "SerializationConflict"]
        rejected_by_validation = [
            r for r in results if not r["accepted"] and r["reason"] != "SerializationConflict"
        ]

        with capsys.disabled():
            print(
                f"\n[{strategy}] accepted={len(accepted)} "
                f"serialization_conflicts={len(conflicts)} "
                f"rejected_by_validation={len(rejected_by_validation)}"
            )

        # Correctness must hold regardless of strategy: at least one bid
        # should get through, the final price must match the HIGHEST
        # accepted bid (no lost update overwrote it with a lower one),
        # and exactly one bid ends up "active" no matter how many
        # sequential winners preceded it.
        assert len(accepted) >= 1, f"[{strategy}] expected at least one accepted bid, got {results}"

        db = SessionLocal()
        auction = db.get(Auction, ids["auction_id"])
        assert auction.current_price == max(r["amount"] for r in accepted)
        active_bids = (
            db.query(Bid)
            .filter(Bid.auction_id == ids["auction_id"], Bid.status == "active")
            .count()
        )
        assert active_bids == 1
        db.close()
    finally:
        cleanup_scenario(
            auction_ids=[ids["auction_id"]], item_ids=[ids["item_id"]],
            user_ids=[ids["seller_id"], *ids["bidder_ids"]],
        )
