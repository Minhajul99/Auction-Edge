from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
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
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
