from sqlalchemy import Column, String, Integer, DateTime, Boolean, Float, Text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime
import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./tripmind.db")

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
Base = declarative_base()


# ─── AUTH ─────────────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id          = Column(String, primary_key=True)
    name        = Column(String, nullable=False)
    email       = Column(String, unique=True, nullable=False, index=True)
    mobile      = Column(String, unique=True, nullable=False)
    password    = Column(String, nullable=False)          # bcrypt hashed
    is_active   = Column(Boolean, default=True)
    created_at  = Column(DateTime, default=datetime.utcnow)


class IRCTCCredential(Base):
    """
    Stores IRCTC login per user.
    Password is AES-256 encrypted before saving.
    NEVER stored in plain text.
    """
    __tablename__ = "irctc_credentials"

    id               = Column(String, primary_key=True)
    user_id          = Column(String, index=True, nullable=False)
    irctc_username   = Column(String, nullable=False)
    irctc_password   = Column(String, nullable=False)   # encrypted
    upi_id           = Column(String, nullable=True)
    created_at       = Column(DateTime, default=datetime.utcnow)
    updated_at       = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ─── TRIPS ────────────────────────────────────────────────────────────────────

class Trip(Base):
    __tablename__ = "trips"

    id             = Column(String, primary_key=True)
    user_id        = Column(String, index=True)
    session_id     = Column(String, index=True)
    origin         = Column(String)
    destination    = Column(String)
    travel_date    = Column(String)
    purpose        = Column(String, nullable=True)
    venue          = Column(String, nullable=True)
    status         = Column(String, default="planning")  # planning/booking/booked/failed
    created_at     = Column(DateTime, default=datetime.utcnow)


class Booking(Base):
    __tablename__ = "bookings"

    id              = Column(String, primary_key=True)
    user_id         = Column(String, index=True)
    trip_id         = Column(String, index=True)
    train_name      = Column(String)
    train_number    = Column(String)
    travel_class    = Column(String)
    departure_time  = Column(String)
    arrival_time    = Column(String)
    price           = Column(Float)
    pnr             = Column(String, nullable=True)
    status          = Column(String, default="pending")  # pending/payment_pending/confirmed/failed
    created_at      = Column(DateTime, default=datetime.utcnow)


class Passenger(Base):
    __tablename__ = "passengers"

    id          = Column(String, primary_key=True)
    user_id     = Column(String, index=True)
    name        = Column(String)
    age         = Column(Integer)
    gender      = Column(String)


class AvailabilityAlert(Base):
    __tablename__ = "availability_alerts"

    id              = Column(String, primary_key=True)
    user_id         = Column(String, index=True)
    train_number    = Column(String)
    train_name      = Column(String)
    travel_date     = Column(String)
    travel_class    = Column(String)
    origin          = Column(String)
    destination     = Column(String)
    is_active       = Column(Boolean, default=True)
    last_checked    = Column(DateTime, nullable=True)
    created_at      = Column(DateTime, default=datetime.utcnow)


# ─── DB INIT ──────────────────────────────────────────────────────────────────

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session