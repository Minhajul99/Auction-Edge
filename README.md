# AuctionEdge

**Verification and Validation of Concurrent State in a Time-Bounded Auction API**
ENGI 9839 — Software Verification and Validation

A full-stack auction platform (FastAPI + PostgreSQL + React) built as the subject
of a systematic V&V exercise: bidding, wallet holds, soft-close timing, and
auto-close all involve concurrency-sensitive invariants that this project
tests deliberately and rigorously, rather than incidentally.

---

## Table of Contents

1. [Tech Stack](#1-tech-stack)
2. [Project Structure](#2-project-structure)
3. [What's Implemented](#3-whats-implemented)
4. [Verification & Validation](#4-verification--validation)
5. [Running the App](#5-running-the-app)
6. [Known Limitations](#6-known-limitations)
7. [Remaining Work](#7-remaining-work)

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
| Testing | pytest, pytest-cov, Hypothesis, mutmut, httpx |
| Environment | Conda env `auction-edge`, Python 3.14 |

---

## 2. Project Structure

```
auction-edge/
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI app, lifespan, router wiring, error handlers
│   │   ├── deps.py                  # get_current_user, get_current_admin (RBAC)
│   │   ├── api/                     # route handlers (auctions, bids, auth, wallet, debug, ws)
│   │   ├── core/                    # business logic -- see table below
│   │   ├── models/                  # SQLAlchemy tables
│   │   ├── schemas/                 # Pydantic request/response shapes
│   │   └── db/database.py           # engine, session, get_db dependency
│   ├── tests/                       # see section 4 -- 142 tests across 5 tiers
│   ├── requirements.txt             # runtime dependencies
│   ├── requirements-dev.txt         # + pytest, hypothesis, mutmut, httpx
│   ├── setup.cfg                    # pytest + mutmut config
│   ├── TESTING.md                   # how to run every test tier
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
├── doccuments/                      # V&V report artifacts (see section 4)
└── docker-compose.yml               # one-command full stack (Postgres + backend + frontend)
```

Core business logic, by file:

| File | Responsibility |
|---|---|
| `core/bidding.py` | Pure bidding logic — tiered increments, soft-close, ties, active-bid limits, Buy It Now validation |
| `core/wallet.py` | Pure wallet logic — available balance, sufficiency check |
| `core/wallet_db.py` | Wallet DB operations — ordered locking, hold, release, charge |
| `core/auto_close.py` | UC5 auto-close sweep (async, scheduler-driven, idempotent) |
| `core/config.py` | `DEBUG_MODE`, `LOCKING_STRATEGY` env toggles |

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
- **Auth**: JWT register/login, bcrypt hashing, protected routes via `get_current_user`
- **Dashboard**: my listings, my bids, notifications, relist button, pay-now button
- **Audit logging**: `bid_placed`, `bid_retracted`, `auction_closed`, `buy_it_now`, `admin_cancelled_bid`
- **Live updates**: WebSocket push on bid placement, retraction, auto-close, and Buy It Now
- **Docker Compose**: one-command full stack
- **Buy It Now**: instant purchase, bypasses timer, closes auction immediately, wallet-integrated
- **Bidder Account Limits**: max 5 active unsettled bids per user
- **Search/Filter/Pagination**: `GET /auctions?category=&min_price=&max_price=&page=&page_size=`
- **RBAC**: `is_admin` flag, admin-only delete-auction and cancel-any-bid endpoints
- **Relisting**: sellers can relist an unsold auction with optional new price/duration
- **Payment stub**: winner's "Pay Now" converts the wallet hold into a real charge
- **Mock Wallet & Bid Hold System**: every bid freezes funds; the `held_amount ≤ balance`
  invariant is enforced even under a literal double-spend attempt (one user, two
  auctions, simultaneous bids)

---

## 4. Verification & Validation

This is the core deliverable of the course project. Full methodology and
technique-to-target mapping lives in `AuctionEdge_Test_Plan.md`; this section
summarizes what was actually built and found.

### Test suite: 142 automated tests across 5 tiers

```
backend/tests/
├── core/          white-box coverage, BVA, equivalence partitioning,
│                  multiple condition coverage, use-case-derived schema validators
├── property/      Hypothesis property-based tests (RQ3)
├── integration/    contract tests, bid/wallet/notification chain, WebSocket
│                  broadcast, state transitions, HTTP-boundary fuzzing
├── concurrency/   race-condition tests, RQ4 locking-strategy comparison
└── system/        full docker-compose stack, real HTTP, real containers
```

See `backend/TESTING.md` for exact commands to run every tier.

### Results by research question

**RQ1 — Race conditions at the auction's closing moment and under simultaneous bids.**
Verified with real concurrent threads (not simulated): no lost updates under
concurrent bidding, the wallet double-spend guard holds under genuine
concurrent access across two auctions, true-timestamp ties resolve to exactly
one winner, and auto-close is idempotent under a repeated/overlapping sweep.

**RQ2 — Mutation testing on boundary-comparison operators (`>` vs `≥`).**
**100/100 mutants killed, 0 survivors** (91 in `core/bidding.py`, 9 in
`core/wallet.py`), via `mutmut` against the BVA-driven test suite.

**RQ3 — Automated edge-case generation for bid and wallet inputs.**
Implemented via Hypothesis (the practical equivalent of symbolic execution
for this input space): 6 property tests, each checking an invariant across
~100 generated examples — `validate_bid` consistency, the Buy-It-Now price
guard, `is_retractable` monotonicity, soft-close never shortening an auction,
and the wallet-hold invariant.

**RQ4 — Comparative analysis: app-level locking (`row_lock`) vs. DB-level
`SERIALIZABLE`.** Same contention scenario run under both strategies:
`row_lock` rejects losing transactions cleanly through validation (0
conflicts); `serializable` lets them race and aborts the loser at commit time
(conflicts observed, requiring client-side retry). Both preserve correctness.
Full numbers in `doccuments/VV Results - RQ1-RQ4.md`.

### Supporting numbers
- Branch coverage on `core/`: **95–96%** overall (100% on `bidding.py`,
  `wallet.py`, `wallet_db.py`, `notifications.py`, `audit.py`)
- Decision table (UC1's alternate flows 3a/4a/5a/6a/6b, traced to specific
  tests): `doccuments/Decision Table - UC1 Place Bid.md`
- Exploratory testing (Saboteur, Antisocial tours): scripted and logged in
  `doccuments/Exploratory Testing Findings.md`

### Bugs found and fixed via testing
- **NaN/Infinity crash**: sending `{"amount": NaN}` (or `Infinity`) to any
  numeric field crashed the server with a 500 instead of a clean validation
  error — FastAPI's default error handler echoes the rejected value back in
  the response, and Starlette's strict JSON encoder can't serialize it.
  Found via HTTP-boundary fuzzing, fixed with a custom exception handler in
  `app/main.py`, verified in both the in-process suite and the real
  containerized system test.

### V&V report artifacts (`doccuments/`)
- `AuctionEdge_Test_Plan.md` — the methodology this suite implements
- `Decision Table - UC1 Place Bid.md`
- `Exploratory Testing Findings.md` — tour scripts + findings log
- `VV Results - RQ1-RQ4.md` — full results writeup, RQ-by-RQ

---

## 5. Running the App

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

> Running the automated test suite? See `backend/TESTING.md` instead — it
> covers `pytest`, mutation testing (needs WSL), and the docker-compose
> system tests separately.

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

### Testing the wallet double-spend scenario manually
1. Register a user — gets a $1000 demo wallet automatically.
2. `GET /wallet/me` → balance 1000, held 0, available 1000.
3. Create two auctions.
4. Bid $900 on auction A → `held_amount` becomes 900, `available` becomes 100.
5. Try to bid $900 on auction B → expect **400 Insufficient Funds** (only $100 available).
6. Retract the bid on auction A → hold releases → now the $900 bid on B succeeds.
7. For the true concurrent version, see `backend/tests/concurrency/test_race_conditions.py`
   (automated) or `scripts/concurrent_bid_test.py` (manual load harness).

---

## 6. Known Limitations
- Proxy/automatic bidding — excluded from v1
- Real payment gateway — stubbed only (wallet is a mock, not a real payment processor)
- Real email verification — assumed via a simple token link, never modeled
- Alembic migrations — schema changes require a manual `DROP SCHEMA` reset (see above)
- Frontend UI for: Buy It Now, search/filter/pagination, RBAC admin actions, wallet — backend-complete, frontend deferred
- No upper bound on bid amount — deliberate (see fuzzing notes in the test suite), not a gap

---

## 7. Remaining Work
- **TLA+ formal specification** — central invariant candidates:
  - No lost bid updates under concurrent access
  - `held_amount ≤ balance` for every user, under any interleaving
  - Auto-close atomicity (never closes while a soft-close-triggering bid is in flight)
- **Exploratory testing execution** — tours are scripted (`doccuments/Exploratory
  Testing Findings.md`) but need to actually be run against the live app and the
  findings log filled in
- **Final report** — structure results around RQ1–RQ4 per the test plan's own
  traceability note, using `doccuments/VV Results - RQ1-RQ4.md` as the base
