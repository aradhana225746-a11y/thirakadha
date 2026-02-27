import uuid
import httpx
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import os

from database import get_db, User, IRCTCCredential, Booking, Trip
from dependencies import get_current_user
from schemas import BookingRequest, BookingStatus
from auth_utils import decrypt_irctc_password, generate_id

router = APIRouter(prefix="/booking", tags=["booking"])

# browser_service runs on port 8001
BROWSER_SERVICE_URL = os.getenv("BROWSER_SERVICE_URL", "http://localhost:8001")


@router.post("/start", response_model=BookingStatus)
async def start_booking(
    body: BookingRequest,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Start automated IRCTC booking.
    - Fetches user's saved IRCTC credentials from DB
    - Decrypts password
    - Sends booking task to browser_service
    - Returns booking_id to poll for status
    """

    # 1. Get IRCTC credentials
    result = await db.execute(
        select(IRCTCCredential).where(IRCTCCredential.user_id == user.id)
    )
    cred = result.scalar_one_or_none()

    if not cred:
        raise HTTPException(
            status_code=400,
            detail="No IRCTC credentials found. Please save your IRCTC username and password in Settings first."
        )

    if not cred.upi_id:
        raise HTTPException(
            status_code=400,
            detail="No UPI ID found. Please add your UPI ID in Settings."
        )

    # 2. Decrypt IRCTC password
    irctc_password = decrypt_irctc_password(cred.irctc_password)

    # 3. Create booking record in DB
    booking_id = generate_id()[:8].upper()
    booking = Booking(
        id=booking_id,
        user_id=user.id,
        trip_id=body.trip_id,
        train_name=body.train_name,
        train_number=body.train_number,
        travel_class=body.travel_class,
        departure_time=body.departure_time,
        arrival_time=body.arrival_time,
        price=body.price,
        status="pending"
    )
    db.add(booking)
    await db.commit()

    # 4. Send to browser_service in background
    background_tasks.add_task(
        trigger_browser_booking,
        booking_id=booking_id,
        irctc_username=cred.irctc_username,
        irctc_password=irctc_password,
        upi_id=cred.upi_id,
        body=body,
        db=db
    )

    return BookingStatus(
        booking_id=booking_id,
        status="started",
        message="🚀 Agent launched! Opening IRCTC..."
    )


async def trigger_browser_booking(
    booking_id: str,
    irctc_username: str,
    irctc_password: str,
    upi_id: str,
    body: BookingRequest,
    db: AsyncSession
):
    """Call browser_service to start the actual browser automation"""
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            await client.post(
                f"{BROWSER_SERVICE_URL}/browser/book",
                json={
                    "booking_id": booking_id,
                    "irctc_username": irctc_username,
                    "irctc_password": irctc_password,
                    "upi_id": upi_id,
                    "train_number": body.train_number,
                    "train_name": body.train_name,
                    "travel_date": body.travel_date,
                    "travel_class": body.travel_class,
                    "origin": body.origin,
                    "destination": body.destination,
                    "passenger_name": body.passenger.name,
                    "passenger_age": body.passenger.age,
                    "passenger_gender": body.passenger.gender
                }
            )
    except Exception as e:
        print(f"Browser service error: {e}")


@router.get("/status/{booking_id}", response_model=BookingStatus)
async def get_booking_status(
    booking_id: str,
    user: User = Depends(get_current_user)
):
    """
    Poll this every 2 seconds from frontend to get live booking status.

    Status flow:
      started → in_progress → payment_pending → confirmed / failed
    """
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(
                f"{BROWSER_SERVICE_URL}/browser/status/{booking_id}"
            )
            data = response.json()
            return BookingStatus(
                booking_id=booking_id,
                status=data.get("status", "unknown"),
                message=data.get("message", ""),
                pnr=data.get("pnr")
            )
    except:
        return BookingStatus(
            booking_id=booking_id,
            status="in_progress",
            message="Agent is working..."
        )


@router.get("/history")
async def booking_history(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get all bookings for the logged-in user"""
    result = await db.execute(
        select(Booking).where(Booking.user_id == user.id)
    )
    bookings = result.scalars().all()
    return {"bookings": [
        {
            "booking_id": b.id,
            "train_name": b.train_name,
            "travel_class": b.travel_class,
            "departure_time": b.departure_time,
            "price": b.price,
            "pnr": b.pnr,
            "status": b.status,
            "created_at": b.created_at
        }
        for b in bookings
    ]}
