import httpx
import os

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID", "")
TELEGRAM_API       = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"


async def send_message(text: str, chat_id: str = None) -> bool:
    target = chat_id or TELEGRAM_CHAT_ID

    if not TELEGRAM_BOT_TOKEN or not target:
        print(f"[TELEGRAM MOCK] {text}")
        return True

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(
                f"{TELEGRAM_API}/sendMessage",
                json={"chat_id": target, "text": text, "parse_mode": "HTML"}
            )
            return r.status_code == 200
    except Exception as e:
        print(f"Telegram error: {e}")
        return False


async def send_booking_confirmation(pnr: str, train_name: str = "", departure: str = ""):
    await send_message(
        f"✅ <b>Ticket Booked!</b>\n\n"
        f"🎫 PNR: <code>{pnr}</code>\n"
        f"🚂 {train_name or 'Your train'}\n"
        f"🕐 {departure or 'As scheduled'}\n\n"
        f"Have a safe journey! 🙏"
    )


async def send_availability_alert(train_name: str, train_number: str, travel_date: str, travel_class: str):
    await send_message(
        f"🔔 <b>Seat Available!</b>\n\n"
        f"🚂 {train_name} ({train_number})\n"
        f"📅 {travel_date} — {travel_class}\n\n"
        f"Open TripMind and book now! ⚡"
    )


async def send_pnr_update(pnr: str, old_status: str, new_status: str):
    emoji = "🎉" if "CNF" in new_status else "⏳"
    await send_message(
        f"{emoji} <b>PNR Update</b>\n\n"
        f"🎫 PNR: <code>{pnr}</code>\n"
        f"📊 {old_status} → <b>{new_status}</b>"
    )


async def send_departure_reminder(train_name: str, pnr: str, departure_time: str):
    await send_message(
        f"⏰ <b>Departure in 2 hours!</b>\n\n"
        f"🚂 {train_name}\n"
        f"🕐 {departure_time}\n"
        f"🎫 PNR: <code>{pnr}</code>\n\n"
        f"Head to the station! 🧳"
    )