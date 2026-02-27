import asyncio
import random
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from services.notification_service import send_availability_alert

# In-memory alert store (backed by DB in production)
active_alerts: dict = {}

scheduler = AsyncIOScheduler()


def start_scheduler():
    """Start the APScheduler background job"""
    scheduler.add_job(
        check_all_alerts,
        trigger="interval",
        minutes=30,
        id="availability_monitor",
        replace_existing=True
    )
    scheduler.start()
    print("✅ Availability scheduler started (every 30 min)")


async def check_all_alerts():
    """Runs every 30 minutes — checks all active alerts"""
    active = {k: v for k, v in active_alerts.items() if v["is_active"]}
    print(f"🔍 Checking {len(active)} availability alerts...")

    for alert_id, alert in active.items():
        try:
            result = await check_availability(
                alert["train_number"],
                alert["travel_date"],
                alert["travel_class"]
            )

            alert["last_checked"] = datetime.utcnow().isoformat()

            if result["available"]:
                print(f"🔔 Seat found: {alert['train_name']} on {alert['travel_date']}")

                await send_availability_alert(
                    alert["train_name"],
                    alert["train_number"],
                    alert["travel_date"],
                    alert["travel_class"]
                )

                # Deactivate after notifying
                alert["is_active"] = False

        except Exception as e:
            print(f"Alert check error ({alert_id}): {e}")


async def check_availability(train_number: str, travel_date: str, travel_class: str) -> dict:
    """
    Check seat availability.
    Hackathon: returns mock data.
    Production: scrape IRCTC or use RailYatri API.
    """
    await asyncio.sleep(0.1)  # Simulate network call
    seats = random.randint(0, 20)
    return {
        "available": seats > 0,
        "seats": seats,
        "status": "AVAILABLE" if seats > 0 else f"WL/{random.randint(1, 50)}"
    }


def add_alert(alert_id: str, user_id: str, train_number: str, train_name: str,
              travel_date: str, travel_class: str, origin: str, destination: str):
    active_alerts[alert_id] = {
        "user_id": user_id,
        "train_number": train_number,
        "train_name": train_name,
        "travel_date": travel_date,
        "travel_class": travel_class,
        "origin": origin,
        "destination": destination,
        "is_active": True,
        "last_checked": None,
        "created_at": datetime.utcnow().isoformat()
    }


def remove_alert(alert_id: str):
    if alert_id in active_alerts:
        active_alerts[alert_id]["is_active"] = False


def get_user_alerts(user_id: str) -> list:
    return [
        {"alert_id": k, **v}
        for k, v in active_alerts.items()
        if v["user_id"] == user_id and v["is_active"]
    ]
