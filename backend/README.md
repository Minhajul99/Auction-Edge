# Running the Test Suite

Before running any tests, run the app itself first — see the section right
below. Once you've confirmed the site actually works end to end, skip down
to **Run the tests**.

## Running the app (do this first)

Two ways to do this — pick one.

### Option A — manual (recommended for just clicking around)

**Prerequisites:** Docker Desktop, Python 3.14, Node.js 18+.

```powershell
# 1. Start Postgres (first time only, create it):
docker run --name auction-postgres -e POSTGRES_PASSWORD=9090 -e POSTGRES_DB=auctionedge -p 5432:5432 -d postgres
# every subsequent time, just:
docker start auction-postgres

# 2. Backend — new terminal
cd auction-edge\backend
python -m pip install -r requirements.txt
uvicorn app.main:app --reload

# 3. Frontend — another new terminal
cd auction-edge\frontend
npm install
npm run dev
```

- Backend: http://127.0.0.1:8000 
- Frontend: http://localhost:5174

Register an account, create a listing, place a bid from a second account
(a different browser or an incognito window works well for this) — that's
enough to confirm the stack is actually working before moving on to the
automated tests below.

### Option B — Docker Compose (one command, backend + frontend + DB together)

```powershell
docker stop auction-postgres   # avoid a port/name clash with compose's own postgres container
cd auction-edge
docker compose up -d --build
```

Same URLs as above. Run `docker compose down` when you're done with it.

> Compose's `postgres` service is also named `auction-postgres`, same as the
> container in Option A — the two can't run at the same time. If you started
> with Option A, stop that container first, per the command above.

---

## One-time setup (for the test suite itself)

```powershell
cd auction-edge\backend
python -m pip install -r requirements-dev.txt
```

The test suite (aside from the `system/` tier) talks to Postgres directly,
not through the frontend — make sure the `auction-postgres` container from
Option A is running:

```powershell
docker start auction-postgres
```

## Run the tests

```powershell
python -m pytest
```

This runs everything except the system tests, which auto-skip unless the full
stack is up, and mutation testing, which needs WSL — see below. You'll get
per-file results and a coverage summary.

### Individual test commands

```powershell
python -m pytest tests/core -v              # white-box/BVA/equivalence -- fast, no DB needed
python -m pytest tests/integration -v       # contract + HTTP-level tests
python -m pytest tests/concurrency -v       # race-condition / RQ4 tests
python -m pytest tests/property -v          # Hypothesis property tests
python -m pytest tests/integration/test_bid_wallet_flow.py -v   # a single file
python -m pytest -k "retract"               # anything with "retract" in the test name
python -m pytest -s                         # don't capture print() output (needed to see
                                             # the row_lock vs serializable comparison printout)
```

> If a bare `pytest ...` command errors with `ModuleNotFoundError: No module
> named 'app'`, use `python -m pytest ...` instead — the `-m` form adds the
> current directory to Python's path, which the app package needs.

## Mutation testing (mutmut) — needs WSL

mutmut doesn't support native Windows. Open a WSL shell:

```powershell
wsl -d Ubuntu
```

then, inside WSL:

```bash
cd "../auction-edge/backend"
python3 -m mutmut run
python3 -m mutmut results
```


## System tests — needs the full stack up

```powershell
cd auction-edge
docker compose up -d --build
cd backend
python -m pytest tests/system -v
docker compose down
```

**Note:** the `auction-postgres` container is normally started manually, not
via `docker compose` — so `docker compose up` will try to create its own
postgres container with the same name and conflict. To run the system tests,
either:

1. Stop and rename your container out of the way first, run compose's own
   stack, then rename/restart your original container afterward, or
2. Just skip this tier — the other 184 tests don't need the full
   docker-compose stack, only the `auction-postgres` container from earlier.

```powershell
# Step by step procedure:
docker stop auction-postgres
docker rename auction-postgres auction-postgres-original
docker compose up -d --build
python -m pytest tests/system -v
docker compose down
docker rename auction-postgres-original auction-postgres
docker start auction-postgres
```

## Test suite layout

```
tests/
├── conftest.py
├── core/            white-box coverage, BVA, equivalence partitioning, MCC,
│                    use-case-derived schema validators (no DB required)
├── property/        Hypothesis property-based tests (RQ3)
├── integration/      contract tests, bid/wallet/notification chain, websockets,
│                    state transitions, HTTP-boundary fuzzing, seller-action
│                    endpoints -- accept-bid/cancel/pay/relist/buy-it-now
│                    (real DB + TestClient)
├── concurrency/     race conditions, RQ4 locking-strategy comparison (real DB, real threads)
└── system/          full docker-compose stack, real HTTP (skips if stack isn't up)
```

188 tests total: 114 in `core/`, 6 in `property/`, 59 in `integration/`,
5 in `concurrency/`, 4 in `system/`.
