from fastapi import APIRouter, Depends
import uuid

from database import User
from dependencies import get_current_user
from schemas import AlertRequest
from services.monitoring_service import add_alert, remove_alert, get_user_alerts
from services.notification_service import send_message

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.post("/alert")
async def create_alert(body: AlertRequest, user: User = Depends(get_current_user)):
    """Set a seat availability alert. User gets Telegram notification when seats open."""

    alert_id = str(uuid.uuid4())[:8]

    add_alert(
        alert_id=alert_id,
        user_id=user.id,
        train_number=body.train_number,
        train_name=body.train_name,
        travel_date=body.travel_date,
        travel_class=body.travel_class,
        origin=body.origin,
        destination=body.destination
    )

    await send_message(
        f"🔔 Alert set!\n"
        f"Train: {body.train_name} ({body.train_number})\n"
        f"Date: {body.travel_date} — {body.travel_class}\n"
        f"You'll be notified when seats open! 💺"
    )

    return {
        "alert_id": alert_id,
        "message": f"Alert set for {body.train_name} on {body.travel_date}. I'll notify you immediately when seats are available!"
    }


@router.delete("/alert/{alert_id}")
async def cancel_alert(alert_id: str, user: User = Depends(get_current_user)):
    remove_alert(alert_id)
    return {"message": "Alert cancelled"}


@router.get("/alerts")
async def get_alerts(user: User = Depends(get_current_user)):
    return {"alerts": get_user_alerts(user.id)}


@router.post("/test")
async def test_notification(user: User = Depends(get_current_user)):
    """Send a test Telegram message to verify notifications are working"""
    success = await send_message(
        f"🧪 TripMind test notification\n"
        f"Hi {user.name}! Alerts are working ✅"
    )
    return {"success": success}