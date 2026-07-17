"""
Concurrent bid load harness for AuctionEdge (RQ1: race conditions).

Fires N simultaneous POST /auctions/{id}/bids requests at the same auction
and reports how many succeeded vs were rejected, plus the final state of
the auction. This is what actually EXERCISES your row-level locking under
real contention — the app code being correct in theory (SELECT FOR UPDATE
serializing access) is a claim; this script is the evidence.

Usage:
    1. Make sure the backend is running (uvicorn ...).
    2. Register N test users first (or reuse existing ones) and note their
       email/password pairs below.
    3. Create one auction to bid on and note its ID.
    4. Run: python concurrent_bid_test.py

Expected correct behavior:
    - Exactly ONE request should end up as the final highest bid.
    - All others should be rejected (400, "someone just beat you to it" /
      minimum increment no longer met) OR succeed as valid higher bids if
      your script sends escalating amounts — see BID_AMOUNTS below.
    - The auction's current_price at the end must equal the highest
      amount among all bids that were accepted, with no lost updates
      (no successfully-submitted higher bid silently overwritten by a
      lower one due to a race).

If you see a HIGHER amount lose to a LOWER one in the final current_price,
that's a genuine concurrency bug — exactly what this harness exists to
catch.
"""

import asyncio
import httpx

BASE_URL = "http://127.0.0.1:8000"

# Fill these in with real registered test accounts before running.
# All bidders send bids at the SAME MOMENT via asyncio.gather, simulating
# true concurrent arrival.
TEST_USERS = [
    {"email": "tester1@example.com", "password": "password123"},
    {"email": "tester2@example.com", "password": "password123"},
    {"email": "tester3@example.com", "password": "password123"},
    {"email": "tester4@example.com", "password": "password123"},
    {"email": "tester5@example.com", "password": "password123"},
]

AUCTION_ID = "REPLACE_WITH_A_REAL_AUCTION_ID"

# Each concurrent bidder submits a different amount, all above the current
# minimum, so at most ONE should win purely on validity + arrival order —
# not because of an invalid amount.
BID_AMOUNTS = [55, 56, 57, 58, 59]


async def login(client: httpx.AsyncClient, email: str, password: str) -> str:
    resp = await client.post(
        f"{BASE_URL}/auth/login",
        data={"username": email, "password": password},
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


async def place_bid(client: httpx.AsyncClient, token: str, auction_id: str, amount: float):
    try:
        resp = await client.post(
            f"{BASE_URL}/auctions/{auction_id}/bids",
            json={"amount": amount},
            headers={"Authorization": f"Bearer {token}"},
        )
        return {"amount": amount, "status_code": resp.status_code, "body": resp.json()}
    except Exception as e:
        return {"amount": amount, "status_code": None, "error": str(e)}


async def main():
    async with httpx.AsyncClient(timeout=10.0) as client:
        print(f"Logging in {len(TEST_USERS)} test users...")
        tokens = await asyncio.gather(
            *[login(client, u["email"], u["password"]) for u in TEST_USERS]
        )

        print(f"Firing {len(tokens)} concurrent bids at auction {AUCTION_ID}...")
        results = await asyncio.gather(
            *[
                place_bid(client, token, AUCTION_ID, amount)
                for token, amount in zip(tokens, BID_AMOUNTS)
            ]
        )

        print("\n--- Results ---")
        for r in results:
            print(r)

        # Verify final auction state
        final = await client.get(f"{BASE_URL}/auctions/{AUCTION_ID}")
        final.raise_for_status()
        final_price = final.json()["current_price"]

        succeeded_amounts = [
            r["amount"] for r in results if r["status_code"] == 201
        ]

        print(f"\nSucceeded amounts: {succeeded_amounts}")
        print(f"Final current_price: {final_price}")

        if succeeded_amounts:
            expected_final = max(succeeded_amounts)
            if float(final_price) == expected_final:
                print("PASS: final price matches the highest successfully accepted bid.")
            else:
                print(
                    f"FAIL: expected final price {expected_final}, "
                    f"got {final_price} — possible lost-update race condition!"
                )
        else:
            print("No bids succeeded — check auction state/minimum increment before running again.")


if __name__ == "__main__":
    asyncio.run(main())
