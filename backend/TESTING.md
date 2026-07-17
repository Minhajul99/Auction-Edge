# Running the Test Suite

## One-time setup

```powershell
cd "D:\Education\1. MUN\Software Validation\Project\Auction Edge\auction-edge\backend"
python -m pip install -r requirements-dev.txt
```

Make sure Postgres is running (the `auction-postgres` container):

```powershell
docker start auction-postgres
```

## Run the tests

```powershell
python -m pytest
```

This runs everything except the system tests (which auto-skip unless the full
stack is up) and mutation testing (which needs WSL — see below). You'll get
per-file results and a coverage summary.

### Useful variations

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

## Mutation testing (mutmut) — needs WSL

mutmut doesn't support native Windows. Open a WSL shell:

```powershell
wsl -d Ubuntu
```

then, inside WSL:

```bash
cd "/mnt/d/Education/1. MUN/Software Validation/Project/Auction Edge/auction-edge/backend"
python3 -m mutmut run
python3 -m mutmut results
```

Config lives in `setup.cfg`'s `[mutmut]` section, scoped to `core/bidding.py`
and `core/wallet.py`, using `tests/core` as the kill oracle.

## System tests — needs the full stack up

```powershell
cd "D:\Education\1. MUN\Software Validation\Project\Auction Edge\auction-edge"
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
   stack, then rename/restart your original container afterward (this is
   what was done the one time these tests were run), or
2. Just skip this tier — the other 138 tests don't need Docker at all.

```powershell
# Option 1, step by step:
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
│                    state transitions, HTTP-boundary fuzzing (real DB + TestClient)
├── concurrency/     race conditions, RQ4 locking-strategy comparison (real DB, real threads)
└── system/          full docker-compose stack, real HTTP (skips if stack isn't up)
```
