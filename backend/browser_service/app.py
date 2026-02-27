import os
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

from booking_agent import book_ticket, get_status

app = FastAPI(
    title="TripMind — Browser Service",
    description="Browser-Use + Playwright IRCTC automation",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── SCHEMAS ──────────────────────────────────────────────────────────────────

class BookingPayload(BaseModel):
    booking_id: str
    irctc_username: str
    irctc_password: str
    upi_id: str
    train_number: str
    train_name: str
    travel_date: str
    travel_class: str
    origin: str
    destination: str
    passenger_name: str
    passenger_age: int
    passenger_gender: str


# ─── ROUTES ───────────────────────────────────────────────────────────────────

@app.post("/browser/book")
async def start_booking(payload: BookingPayload, background_tasks: BackgroundTasks):
    """
    Receives booking request from core_service.
    Launches browser-use agent in background.
    IRCTC credentials are decrypted by core_service before sending here.
    This service never touches the DB — it only runs the browser.
    """
    background_tasks.add_task(
        book_ticket,
        booking_id=payload.booking_id,
        irctc_username=payload.irctc_username,
        irctc_password=payload.irctc_password,
        upi_id=payload.upi_id,
        train_number=payload.train_number,
        train_name=payload.train_name,
        travel_date=payload.travel_date,
        travel_class=payload.travel_class,
        origin=payload.origin,
        destination=payload.destination,
        passenger_name=payload.passenger_name,
        passenger_age=payload.passenger_age,
        passenger_gender=payload.passenger_gender
    )

    return {
        "booking_id": payload.booking_id,
        "status": "started",
        "message": "Browser agent launched"
    }


@app.get("/browser/status/{booking_id}")
async def booking_status(booking_id: str):
    """
    Polled by core_service every 2 seconds.
    Returns live status of the browser agent.

    Status flow:
      in_progress → payment_pending → confirmed / failed
    """
    status = get_status(booking_id)

    if status["status"] == "not_found":
        raise HTTPException(status_code=404, detail="Booking not found")

    return status


@app.get("/")
async def root():
    return {"service": "TripMind Browser Service", "status": "running", "port": 8001}


@app.get("/health")
async def health():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8001, reload=False)
    # reload=False because browser agents don't work well with hot reload
