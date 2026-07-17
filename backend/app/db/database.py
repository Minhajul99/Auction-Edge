import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Falls back to your existing local Postgres setup if DATABASE_URL isn't set
# (e.g. running uvicorn directly on your machine, outside Docker).
# Inside docker-compose, DATABASE_URL is overridden to point at the
# 'postgres' service name instead of localhost.
DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://postgres:9090@localhost:5432/auctionedge"
)

engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """FastAPI dependency: yields a DB session and closes it after the request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
