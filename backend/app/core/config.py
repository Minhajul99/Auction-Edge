"""
Central config, read from environment variables so behavior can be
switched without code changes (e.g. between local dev, testing, and a
"never enable this in a real deployment" debug mode).
"""

import os

# Enables debug-only endpoints (time injection, tied-bid injection).
# Must be explicitly "true" — defaults to disabled so these never
# accidentally ship enabled.
DEBUG_MODE = os.getenv("AUCTIONEDGE_DEBUG", "false").lower() == "true"

# Which concurrency-control strategy place_bid uses. This is the toggle
# for your proposal's "Comparative Analysis" outcome — run your test suite
# against both and compare results.
#   "row_lock"    -> SELECT ... FOR UPDATE (default, app-level pessimistic lock)
#   "serializable" -> Postgres SERIALIZABLE isolation (DB-level, optimistic;
#                     conflicting transactions are aborted and must retry)
LOCKING_STRATEGY = os.getenv("AUCTIONEDGE_LOCKING_STRATEGY", "row_lock")
