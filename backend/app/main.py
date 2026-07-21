import math
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.db.database import engine, Base
from app.models import User, Item, Auction, Bid, Notification, AuditLogEntry, Wallet
from app.api import users, auctions, bids, notifications, auth, websockets, debug, wallet
from app.core.auto_close import close_expired_auctions

scheduler = AsyncIOScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: create tables, start the UC5 auto-close scheduler
    Base.metadata.create_all(bind=engine)
    scheduler.add_job(close_expired_auctions, "interval", seconds=10, id="auto_close")
    scheduler.start()
    yield
    # Shutdown
    scheduler.shutdown()


app = FastAPI(
    title="AuctionEdge API",
    description="Time-bounded auction API — race conditions, timing, and V&V focus.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5174", "http://127.0.0.1:5174"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def _sanitize_non_json_floats(value):
    """
    Replace any NaN/Infinity float with its string form. Starlette's
    JSONResponse serializes with allow_nan=False (strict RFC 8259), but
    FastAPI's default validation-error response echoes the raw rejected
    input back in each error's "input" field -- if a client sends a
    NaN/Infinity value for a numeric field, that raw float ends up in the
    error body and crashes the response encoder with an unhandled
    ValueError (a client-caused 500, discovered via HTTP-level fuzzing of
    the bid endpoint). Sanitizing here fixes it for every endpoint, since
    every request body is validated the same way.
    """
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return str(value)
    if isinstance(value, dict):
        return {k: _sanitize_non_json_floats(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_sanitize_non_json_floats(v) for v in value]
    return value


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = _sanitize_non_json_floats(jsonable_encoder(exc.errors()))
    return JSONResponse(status_code=422, content={"detail": errors})


app.include_router(auth.router)
app.include_router(users.router)
app.include_router(auctions.router)
app.include_router(bids.router)
app.include_router(notifications.router)
app.include_router(websockets.router)
app.include_router(debug.router)
app.include_router(wallet.router)


@app.get("/")
def read_root():
    return {"message": "AuctionEdge API is running"}


@app.get("/health")
def health_check():
    return {"status": "ok"}
