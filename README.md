# AuctionEdge

**Verification and Validation of Concurrent State in a Time-Bounded Auction API**
ENGI 9839 — Software Verification and Validation

A full-stack auction platform (FastAPI + PostgreSQL + React) built as the subject of a
systematic V&V exercise: bidding, wallet holds, soft-close timing, and auto-close all
involve concurrency-sensitive invariants that this project tests deliberately and
rigorously, rather than incidentally.

---

## Table of Contents

1. [Tech Stack](#tech-stack)
2. [Project Structure](#project-structure)
3. [Features](#features)
4. [Getting Started](#getting-started)
5. [Configuration](#configuration)
6. [Testing](#testing)
7. [API Overview](#api-overview)
8. [Known Limitations](#known-limitations)
9. [License](#license)

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI (Python 3.14), SQLAlchemy 2.0 (typed `Mapped[]` style) |
| Database | PostgreSQL (via Docker) |
| Frontend | React 19 (Vite), Tailwind CSS, React Router |
| Auth | JWT (PyJWT), bcrypt password hashing (via passlib) |
| Real-time | Native WebSockets (FastAPI `WebSocket`, browser `WebSocket` API) |
| Scheduling | APScheduler (`AsyncIOScheduler`) for auction auto-close |
| Testing | pytest, pytest-cov, Hypothesis, mutmut, httpx |

---

## Project Structure

```
auction-edge/
├── backend/
│   ├── app/
│   │   ├── main.py           # FastAPI app, lifespan, router wiring, error handlers
│   │   ├── deps.py           # get_current_user, get_current_admin (RBAC)
│   │   ├── api/               # route handlers (auctions, bids, auth, wallet, notifications, ws, debug)
│   │   ├── core/              # business logic (bidding, wallet, auto-close, auth, config, audit)
│   │   ├── models/            # SQLAlchemy tables
│   │   ├── schemas/           # Pydantic request/response shapes
│   │   └── db/database.py     # engine, session, get_db dependency
│   ├── tests/                 # 188 tests across 5 tiers -- see backend/README.md
│   ├── requirements-dev.txt   # + pytest, hypothesis, mutmut, httpx
│   ├── setup.cfg               # pytest + mutmut config
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── pages/              # Browse, ItemDetail, CreateListing, Login, Dashboard
│   │   ├── components/         # PaymentModal, Toast
│   │   ├── context/AuthContext.jsx   # JWT storage, login/register/logout
│   │   ├── hooks/useAuctionSocket.js
│   │   ├── services/api.js     # centralized fetch wrapper, auto-attaches JWT
│   │   └── App.jsx             # routing, nav bar
│   └── Dockerfile
├── scripts/
│   └── concurrent_bid_test.py  # standalone race-condition load harness
├── requirements.txt             # backend runtime dependencies
└── docker-compose.yml            # one-command full stack (Postgres + backend + frontend)
```

Core backend business logic, by file:

| File | Responsibility |
|---|---|
| `core/bidding.py` | Pure bidding logic — tiered increments, soft-close, ties, active-bid limits, Buy It Now validation |
| `core/wallet.py` | Pure wallet logic — available balance, sufficiency check |
| `core/wallet_db.py` | Wallet DB operations — ordered locking, hold, release, charge |
| `core/auto_close.py` | Auto-close sweep (async, scheduler-driven, idempotent) |
| `core/config.py` | `DEBUG_MODE`, `LOCKING_STRATEGY` env toggles |

---

## Features

- **Bidding** — tiered minimum increments, self-outbid prevention, soft-close time
  extension, atomic row-locking under concurrency, wallet hold on every bid
- **Bid retraction** — 15-minute window from the original bid timestamp, one
  retraction per bid, releases the associated wallet hold
- **Auction listings** — category enum, duration presets, optional reserve price,
  optional Buy It Now price
- **Buy It Now** — instant purchase that bypasses the timer, closes the auction
  immediately, wallet-integrated
- **Auto-close** — scheduled sweep that atomically and idempotently resolves
  expired auctions into Sold / No Bids / Reserve Not Met
- **Wallet & bid holds** — every bid freezes funds; `held_amount ≤ balance` is
  enforced even under concurrent bidding across multiple auctions
- **Notifications** — outbid, won, lost, and reserve-met events, pushed live over
  WebSocket and viewable from the dashboard
- **Auth & RBAC** — JWT register/login, bcrypt hashing, admin-only endpoints
  (cancel any bid, delete an auction)
- **Search / filter / pagination** — `GET /auctions?category=&min_price=&max_price=&page=&page_size=`
- **Relisting** — sellers can relist an unsold auction with an optional new price/duration
- **Payment** — a winner's "Pay Now" converts their wallet hold into a real charge
- **Audit logging** — `bid_placed`, `bid_retracted`, `auction_closed`, `buy_it_now`, `admin_cancelled_bid`

---

## Getting Started

**Prerequisites:** Docker Desktop, Python 3.14, Node.js 18+.

### Option A — manual (recommended for local development)

```powershell
# 1. Start Postgres (first time only, create it):
docker run --name auction-postgres -e POSTGRES_PASSWORD=9090 -e POSTGRES_DB=auctionedge -p 5432:5432 -d postgres
# every subsequent time, just:
docker start auction-postgres

# 2. Backend -- new terminal
cd backend
python -m pip install -r ../requirements.txt
uvicorn app.main:app --reload

# 3. Frontend -- another new terminal
cd frontend
npm install
npm run dev
```

- Backend: http://127.0.0.1:8000 (Swagger docs at `/docs`)
- Frontend: http://localhost:5173

Register an account, create a listing, then place a bid from a second account
(a different browser or an incognito window works well) to confirm the stack
is working end to end.

### Option B — Docker Compose (one command, backend + frontend + DB together)

```powershell
docker stop auction-postgres   # avoid a port/name clash with compose's own postgres container
docker compose up -d --build
```

Same URLs as above. Run `docker compose down` when you're done.

> Compose's `postgres` service is also named `auction-postgres`, same as the
> container in Option A — the two can't run at the same time.

### Resetting the database schema

No Alembic migrations are set up — whenever a model gains a new column/table,
wipe and let `create_all()` rebuild:

```powershell
docker exec -it auction-postgres psql -U postgres -d auctionedge -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
```

Then restart `uvicorn`.

### Promoting a user to admin

No admin-signup UI exists on purpose — promote manually:

```powershell
docker exec -it auction-postgres psql -U postgres -d auctionedge -c "UPDATE users SET is_admin = true WHERE email = 'your@email.com';"
```

---

## Configuration

Environment variables (all optional, safe defaults):

| Variable | Default | Purpose |
|---|---|---|
| `AUCTIONEDGE_DEBUG` | `false` | Enables debug-only endpoints (time injection, tied-bid injection) |
| `AUCTIONEDGE_LOCKING_STRATEGY` | `row_lock` | Bid concurrency control: `row_lock` (`SELECT ... FOR UPDATE`) or `serializable` (Postgres `SERIALIZABLE` isolation) |
| `DATABASE_URL` | local Postgres | Overridden by `docker-compose.yml` to point at the `postgres` service |

```powershell
$env:AUCTIONEDGE_DEBUG = "true"
$env:AUCTIONEDGE_LOCKING_STRATEGY = "serializable"
```

Both reset to defaults in a fresh terminal — that's intentional (safe by default).

---

## Testing

The backend test suite has 188 tests across 5 tiers (unit/white-box, property-based,
integration, concurrency, and full-stack system tests), plus mutation testing on the
boundary-sensitive bidding/wallet logic.

Full setup and commands, including the docker-compose system-test procedure and WSL
mutation-testing steps, are documented in **[backend/README.md](backend/README.md)**.
Quick start once Postgres is running:

```powershell
cd backend
python -m pip install -r requirements-dev.txt
python -m pytest
```

---

## API Overview

Interactive docs are available at `/docs` (Swagger UI) once the backend is running.
Main resource groups:

| Prefix | Purpose |
|---|---|
| `/auth` | Register, login |
| `/auctions` | Create, browse (search/filter/pagination), close, relist, admin delete |
| `/bids` | Place bid, retract bid, view bid history, Buy It Now, admin cancel |
| `/wallet` | View balance/holds, pay for a won auction |
| `/notifications` | List a user's notifications |
| `/ws` | WebSocket endpoint for live auction updates |

---

## Known Limitations

- Proxy/automatic bidding is out of scope for v1
- The wallet is a mock — payments are simulated, not routed through a real gateway
- Email verification is assumed via a simple token link, never fully modeled
- No Alembic migrations — schema changes require a manual schema reset (see above)
- No upper bound on bid amount — deliberate, not an oversight

---

## License

All rights reserved to Md Minhajul Abedin & Nabil Hasan.
