from pydantic import BaseModel, EmailStr
from typing import Optional, List


# ─── AUTH SCHEMAS ─────────────────────────────────────────────────────────────

class SignupRequest(BaseModel):
    name: str
    email: EmailStr
    mobile: str
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    name: str
    email: str


class IRCTCCredentialRequest(BaseModel):
    irctc_username: str
    irctc_password: str
    upi_id: Optional[str] = None


class IRCTCCredentialResponse(BaseModel):
    message: str
    irctc_username: str   # return username only, never password


# ─── CHAT SCHEMAS ─────────────────────────────────────────────────────────────

class ChatMessage(BaseModel):
    message: str
    session_id: str


class TrainOption(BaseModel):
    train_name: str
    train_number: str
    departure_time: str
    arrival_time: str
    duration: str
    travel_class: str
    price: float
    availability: str


class TripPlan(BaseModel):
    origin: str
    destination: str
    travel_date: str
    purpose: Optional[str] = None
    venue: Optional[str] = None
    train_options: List[TrainOption] = []


class ChatResponse(BaseModel):
    reply: str
    type: str          # question / options / booking_started / info / alert_set
    trip_plan: Optional[TripPlan] = None
    session_id: str


# ─── BOOKING SCHEMAS ──────────────────────────────────────────────────────────

class PassengerDetails(BaseModel):
    name: str
    age: int
    gender: str        # M / F / T


class BookingRequest(BaseModel):
    trip_id: str
    train_number: str
    train_name: str
    travel_class: str
    departure_time: str
    arrival_time: str
    price: float
    origin: str
    destination: str
    travel_date: str
    passenger: PassengerDetails


class BookingStatus(BaseModel):
    booking_id: str
    status: str
    message: str
    pnr: Optional[str] = None


# ─── ALERT SCHEMAS ────────────────────────────────────────────────────────────

class AlertRequest(BaseModel):
    train_number: str
    train_name: str
    travel_date: str
    travel_class: str
    origin: str
    destination: str
