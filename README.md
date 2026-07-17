# AuctionEdge

**Verification and Validation of Concurrent State in a Time-Bounded Auction API**
ENGI 9839: Software Verification and Validation

---

## 1. Tech Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI (Python 3.14), SQLAlchemy 2.0 (typed `Mapped[]` style) |
| Database | PostgreSQL (via Docker) |
| Frontend | React (Vite), plain CSS, React Router |
| Auth | JWT (PyJWT), bcrypt password hashing (via passlib) |
| Real-time | Native WebSockets (FastAPI `WebSocket`, browser `WebSocket` API) |
| Scheduling | APScheduler (`AsyncIOScheduler`) for UC5 auto-close |
| Environment | Conda env `auction-edge`, Python 3.14 |

---

## 2. Project Structure

```
auction-edge/
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI app, lifespan, router wiring
│   │   ├── deps.py                  # get_current_user, get_current_admin (RBAC)
│   │   ├── api/
│   │   │   ├── auth.py              # /auth/register (+ wallet creation), /auth/login
│   │   │   ├── users.py             # public profile lookup
│   │   │   ├── auctions.py          # UC2, browse/search/pagination, relist, Buy It Now,
│   │   │   │                        # pay, admin delete
│   │   │   ├── bids.py              # UC1, UC3, UC4, admin-cancel, my-bids
│   │   │   ├── notifications.py     # UC6, /users/me/notifications
│   │   │   ├── wallet.py            # /wallet/me, /wallet/deposit (demo top-up)
│   │   │   ├── websockets.py        # /ws/auctions/{id} live updates
│   │   │   ├── ws_manager.py        # WebSocket connection manager
│   │   │   └── debug.py             # DEBUG-ONLY: time injection, tied-bid injection
│   │   ├── core/
│   │   │   ├── bidding.py           # PURE bidding logic (increments, soft-close, ties,
│   │   │   │                        # limits, Buy It Now validation)
│   │   │   ├── wallet.py            # PURE wallet logic (available balance, sufficiency)
│   │   │   ├── wallet_db.py         # wallet DB ops: locking, hold, release, charge
│   │   │   ├── auto_close.py        # UC5 auto-close sweep (async, scheduler-driven)
│   │   │   ├── notifications.py     # notification-creation helper
│   │   │   ├── audit.py             # audit-log-entry helper
│   │   │   ├── auth.py              # password hashing, JWT encode/decode
│   │   │   └── config.py            # DEBUG_MODE, LOCKING_STRATEGY env toggles
│   │   ├── models/                  # SQLAlchemy tables: User, Item, Auction, Bid,
│   │   │                            # Notification, AuditLogEntry, Wallet
│   │   ├── schemas/                 # Pydantic request/response shapes
│   │   └── db/database.py           # engine, session, get_db dependency
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── pages/                   # Browse, ItemDetail, CreateListing, Login, Dashboard
│   │   ├── context/AuthContext.jsx  # JWT storage, login/register/logout
│   │   ├── hooks/useAuctionSocket.js
│   │   ├── services/api.js          # centralized fetch wrapper, auto-attaches JWT
│   │   └── App.jsx                  # routing, nav bar
│   └── Dockerfile
├── scripts/
│   └── concurrent_bid_test.py       # standalone race-condition load harness
└── docker-compose.yml               # one-command full stack (Postgres + backend + frontend)
```

> **Frontend note:** Buy It Now, search/filter/pagination, RBAC admin actions, and the
> wallet are currently backend-only (testable via Swagger). Frontend UI for these is
> deferred until after the testing phase.

---

## 3. What's Implemented

### Core Use Cases (UC1–UC6)
| UC | Feature | Key file(s) |
|---|---|---|
| UC1 | Place Bid — tiered increments, self-outbid block, soft-close extension, row-locking, wallet hold | `core/bidding.py`, `core/wallet_db.py`, `api/bids.py` |
| UC2 | Create Auction Listing — category enum, duration presets, reserve validation, optional Buy It Now price | `api/auctions.py` |
| UC3 | Retract Bid — 15-min window from original timestamp, one retraction per bid, releases wallet hold | `core/bidding.py`, `api/bids.py` |
| UC4 | View Bid History — masked bidder identities, consistent per-item | `api/bids.py` |
| UC5 | Auction Auto-Close — atomic + idempotent, 3 outcomes (Sold/NoBids/ReserveNotMet), releases holds on unsold | `core/auto_close.py` |
| UC6 | Outbid/Won/Lost/Reserve-Met Notifications | `core/notifications.py` |

### Beyond the core use cases
- **Auth**: JWT register/login, bcrypt hashing, first/last name, protected routes via `get_current_user`
- **Dashboard**: my listings, my bids, notifications, relist button, pay-now button
- **Audit logging**: `bid_placed`, `bid_retracted`, `auction_closed`, `buy_it_now`, `admin_cancelled_bid` — all logged with IP where applicable
- **Live updates**: WebSocket push on bid placement, retraction, auto-close, and Buy It Now
- **Docker Compose**: one-command full stack
- **Photo upload**: client-side file → base64, displayed on Browse/Item Detail
- **Buy It Now**: instant purchase, bypasses timer, closes auction immediately, wallet-integrated
- **Bidder Account Limits**: max 5 active unsettled bids per user (`exceeds_active_bid_limit`)
- **Search/Filter/Pagination**: `GET /auctions?category=&min_price=&max_price=&page=&page_size=`
- **RBAC**: `is_admin` flag, admin-only delete-auction and cancel-any-bid endpoints (401 vs 403 distinction preserved)
- **Relisting**: sellers can relist an unsold auction with optional new price/duration
- **Payment stub**: winner can "Pay Now" — now actually finalizes the wallet charge (converts hold → real deduction), not just a status flag
- **Mock Wallet & Bid Hold System**: every bid freezes funds; outbid/retracted/cancelled releases the hold; winning holds convert to real charges only on payment; unsold auctions return the hold. Prevents double-spending across simultaneous bids on different auctions.

### Testing infrastructure (built for the V&V research questions)

**RQ1 — Race conditions at the auction's closing moment:**
- `.with_for_update()` row-locking on `Auction` (default) and `Wallet` rows
- `lock_wallets_in_order()` — wallets are always locked in a **fixed, sorted order** across any transaction touching more than one, specifically to prevent deadlock when a bid transaction must lock both the new bidder's and the previous highest bidder's wallets
- **Wallet hold invariant**: `held_amount ≤ balance` for every user, at all times — must hold even under a literal double-spend attempt (one user, two auctions, same instant)
- `resolve_tie()` in `core/bidding.py` — pure, deterministic tie-break for the "true simultaneous arrival, identical timestamp" case
- Debug endpoints (`api/debug.py`, gated behind `AUCTIONEDGE_DEBUG=true`):
  - `PATCH /debug/auctions/{id}/end-time` — force an auction's end time to any value
  - `POST /debug/auctions/run-auto-close` — trigger UC5's closure sweep immediately
  - `POST /debug/auctions/{id}/inject-tied-bids` — create two bids with an identical timestamp (impossible via the real API)
  - `POST /debug/auctions/{id}/resolve-tie` — apply `resolve_tie()` to an injected tie
- `scripts/concurrent_bid_test.py` — fires N simultaneous bid requests via `asyncio.gather`; reports whether the final price matches the highest successfully accepted bid (any mismatch = a real lost-update bug). Can also be pointed at the same user bidding on two different auctions simultaneously, to test the wallet double-spend invariant directly.
- **Pluggable locking strategy** (`AUCTIONEDGE_LOCKING_STRATEGY` env var):
  - `row_lock` (default) — app-level `SELECT ... FOR UPDATE`
  - `serializable` — DB-level `SERIALIZABLE` isolation; conflicting transactions get `409` and must retry
  - Run the load harness against both and compare — this is the report's comparative-analysis content

**RQ2 — Mutation testing (`>` vs `≥`):**
- `bid_meets_minimum(bid_amount, required_min)` — isolated one-line comparison in `core/bidding.py`
- `exceeds_active_bid_limit(count)` — isolated boundary check (bid #5 succeeds, #6 fails)
- `has_sufficient_funds(balance, held, amount)` — isolated wallet comparison in `core/wallet.py`
- All three are deliberately separated from surrounding control flow so `mutmut` has a single unambiguous operator to flip, and your test suite can target each in isolation

**RQ3 — Symbolic execution / edge-case bid inputs:**
- `validate_bid()`, `validate_buy_it_now()`, `is_retractable()`, `compute_new_end_time()` — all pure functions with explicit branches, no I/O
- Negative prices and `page=0` rejected at the FastAPI/Pydantic layer (`Query(ge=0)`, `Query(ge=1)`) before the function body runs — a clean boundary for input-generation tools
- Boundary values worth testing: retraction at 14:59 / 15:00 / 15:01, soft-close bid at exactly 3:00 / 2:59 remaining, wallet hold at exactly available balance vs available − 0.01

---

## 4. How to Run

### Option A — manual (your original workflow)
```powershell
# 1. Start Postgres
docker start auction-postgres
# (first time only: docker run --name auction-postgres -e POSTGRES_PASSWORD=9090 -e POSTGRES_DB=auctionedge -p 5432:5432 -d postgres)

# 2. Backend
cd backend
conda activate auction-edge
uvicorn app.main:app --reload

# 3. Frontend (separate terminal)
cd frontend
npm run dev
```
Backend: http://127.0.0.1:8000 (Swagger docs at `/docs`)
Frontend: http://localhost:5173

### Option B — Docker Compose (one command)
```powershell
docker stop auction-postgres   # avoid port clash with compose's own postgres
cd auction-edge
docker-compose up --build
```

### Resetting the database schema
No Alembic migrations set up — whenever a model gains a new column/table, wipe and let `create_all()` rebuild:
```powershell
docker exec -it auction-postgres psql -U postgres -d auctionedge -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
```
Then restart `uvicorn`.

### Promoting a user to admin (for RBAC testing)
No admin-signup UI exists on purpose — promote manually:
```powershell
docker exec -it auction-postgres psql -U postgres -d auctionedge -c "UPDATE users SET is_admin = true WHERE email = 'your@email.com';"
```

### Enabling debug/testing endpoints
Disabled by default (returns 404 if not set):
```powershell
$env:AUCTIONEDGE_DEBUG = "true"
```

### Switching locking strategy
```powershell
$env:AUCTIONEDGE_LOCKING_STRATEGY = "serializable"   # default is "row_lock"
```
Both env vars reset to defaults in a fresh terminal — that's intentional (safe by default).

### Running the concurrent load test
```powershell
pip install httpx
cd scripts
# Edit TEST_USERS and AUCTION_ID at the top of the file first
python concurrent_bid_test.py
```

### Testing the wallet double-spend scenario
1. Register a user — gets a $1000 demo wallet automatically.
2. `GET /wallet/me` → balance 1000, held 0, available 1000.
3. Create two auctions.
4. Bid $900 on auction A → `held_amount` becomes 900, `available` becomes 100.
5. Try to bid $900 on auction B → expect **400 Insufficient Funds** (only $100 available).
6. Retract the bid on auction A → hold releases → now the $900 bid on B succeeds.
7. For the true concurrent version: use `concurrent_bid_test.py` with the *same user* bidding on *two different auctions* at once with amounts that together exceed their balance. Exactly one request should succeed.

---

## 5. Known Gaps (deliberately out of scope, per client interview decisions)
- Proxy/automatic bidding — excluded from v1
- Real payment gateway — stubbed only (wallet is a mock, not a real payment processor)
- Real email verification — assumed via a simple token link, never modeled
- Alembic migrations — schema changes require a manual `DROP SCHEMA` reset (see above)
- Frontend UI for: Buy It Now, search/filter/pagination, RBAC admin actions, wallet — backend-complete, frontend deferred

---

## 6. Next Steps
- TLA+ formal specification — central invariant candidates:
  - No lost bid updates under concurrent access
  - `held_amount ≤ balance` for every user, under any interleaving (the double-spend invariant)
  - Auto-close atomicity (never closes while a soft-close-triggering bid is in flight)
- `pytest` unit test suite against `core/bidding.py`, `core/wallet.py`, `core/auto_close.py`
- Mutation testing (`mutmut`) against the isolated comparison functions (RQ2)
- Symbolic execution / automated edge-case generation for bid inputs and wallet amounts (RQ3)
