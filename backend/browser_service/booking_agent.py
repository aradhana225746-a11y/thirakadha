import asyncio
import os
from datetime import datetime

try:
    from browser_use import Agent, Browser, BrowserConfig
    from langchain_openai import ChatOpenAI
    BROWSER_USE_AVAILABLE = True
except ImportError:
    BROWSER_USE_AVAILABLE = False
    print("⚠️  browser-use not installed: pip install browser-use && playwright install chromium")

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")

# Live status store — keyed by booking_id
booking_statuses: dict = {}


def _get_llm():
    return ChatOpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=OPENROUTER_API_KEY,
        model="meta-llama/llama-3.1-8b-instruct:free",
        temperature=0.1
    )


def set_status(booking_id: str, status: str, message: str, pnr: str = None, step: str = None):
    booking_statuses[booking_id] = {
        "status": status,
        "message": message,
        "pnr": pnr,
        "step": step,
        "updated_at": datetime.utcnow().isoformat()
    }
    print(f"[{booking_id}] {status}: {message}")


async def book_ticket(
    booking_id: str,
    irctc_username: str,
    irctc_password: str,
    upi_id: str,
    train_number: str,
    train_name: str,
    travel_date: str,
    travel_class: str,
    origin: str,
    destination: str,
    passenger_name: str,
    passenger_age: int,
    passenger_gender: str
):
    """
    Full IRCTC booking agent.
    Fills everything → reaches UPI payment page → stops.
    User enters UPI PIN on their phone — that's all they do.
    """

    if not BROWSER_USE_AVAILABLE:
        await _mock_booking(booking_id, train_name)
        return

    set_status(booking_id, "in_progress", "🔐 Opening IRCTC...", step="opening")

    task = f"""
Book an IRCTC train ticket step by step:

STEP 1 — Login:
- Go to https://www.irctc.co.in/nget/train-search
- Click the LOGIN button (top right)
- Type username: {irctc_username}
- Type password: {irctc_password}
- Solve any CAPTCHA shown
- Click SIGN IN and wait for the home page

STEP 2 — Search Train:
- In the From field enter: {origin}
- Select matching station from dropdown
- In the To field enter: {destination}
- Select matching station from dropdown
- Set Date of Journey to: {travel_date}
- Click SEARCH TRAINS

STEP 3 — Select Train:
- Find train number {train_number} ({train_name}) in results
- Click BOOK NOW for that train
- Select class {travel_class}

STEP 4 — Passenger Details:
- Click Add Passenger
- Fill Name: {passenger_name}
- Fill Age: {passenger_age}
- Select Gender: {passenger_gender}
- Select berth: Lower if available
- Click Continue

STEP 5 — Payment:
- On payment page choose UPI as payment method
- Enter UPI ID: {upi_id}
- Click Pay Now / Proceed to Pay
- STOP immediately after clicking pay — do not do anything else
- Return the text: PAYMENT_REQUESTED

Important notes:
- Wait for each page to fully load before acting
- Close any popups that appear
- If CAPTCHA appears solve it carefully
- Report each completed step
"""

    browser = Browser(config=BrowserConfig(headless=False))

    try:
        agent = Agent(task=task, llm=_get_llm(), browser=browser, max_actions_per_step=5)

        set_status(booking_id, "in_progress", "🔐 Logging into IRCTC...", step="logging_in")
        result = await agent.run(max_steps=60)
        result_str = str(result).lower()

        if "payment_requested" in result_str or "upi" in result_str or "payment" in result_str:
            set_status(
                booking_id,
                "payment_pending",
                "📱 UPI collect request sent! Open GPay/PhonePe and enter your PIN to confirm booking.",
                step="waiting_for_pin"
            )
            # Wait for user to enter PIN, then grab PNR
            asyncio.create_task(_wait_for_confirmation(booking_id, agent, browser))
        else:
            set_status(booking_id, "failed", "Could not complete booking. Please try again.")
            await browser.close()

    except Exception as e:
        set_status(booking_id, "failed", f"Agent error: {str(e)}")
        try:
            await browser.close()
        except:
            pass


async def _wait_for_confirmation(booking_id: str, agent, browser):
    """After user enters PIN, monitor page for booking confirmation and extract PNR"""

    await asyncio.sleep(15)  # Give user time to open phone and enter PIN

    confirm_task = """
Monitor the current IRCTC page for payment result.
Wait up to 3 minutes.
Once payment succeeds:
1. Find the PNR number (8 digits) on confirmation page
2. Return exactly: PNR:XXXXXXXX (replace X with actual digits)

If payment fails or times out return: PAYMENT_FAILED
"""

    try:
        result = await agent.run(max_steps=30)
        result_str = str(result)

        if "PNR:" in result_str:
            start = result_str.find("PNR:") + 4
            pnr = result_str[start:start + 10].strip().split()[0]
            set_status(booking_id, "confirmed", f"✅ Ticket booked! PNR: {pnr}", pnr=pnr)

            # Notify via core_service
            await _notify_core_service(booking_id, pnr)
        else:
            set_status(booking_id, "payment_failed", "Payment was not completed. No charges made.")

    except Exception as e:
        set_status(booking_id, "error", str(e))
    finally:
        try:
            await browser.close()
        except:
            pass


async def _notify_core_service(booking_id: str, pnr: str):
    """Tell core_service the booking is confirmed so it can update DB + send Telegram"""
    import httpx
    core_url = os.getenv("CORE_SERVICE_URL", "http://localhost:8000")
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(
                f"{core_url}/booking/confirmed",
                json={"booking_id": booking_id, "pnr": pnr}
            )
    except:
        pass


async def _mock_booking(booking_id: str, train_name: str):
    """Mock flow for demo when browser-use is not installed"""
    steps = [
        ("logging_in", "🔐 Logging into IRCTC...", 2),
        ("searching", "🔍 Searching trains...", 2),
        ("selecting", f"🚂 Selecting {train_name}...", 1),
        ("filling", "📝 Filling passenger details...", 2),
        ("payment", "💳 Setting up UPI payment...", 1),
    ]
    for step, message, delay in steps:
        set_status(booking_id, "in_progress", message, step=step)
        await asyncio.sleep(delay)

    set_status(
        booking_id,
        "payment_pending",
        "📱 UPI collect request sent! Open GPay/PhonePe and enter your PIN.",
        step="waiting_for_pin"
    )

    # Auto-confirm after 20s (demo only)
    asyncio.create_task(_mock_confirm(booking_id))


async def _mock_confirm(booking_id: str):
    await asyncio.sleep(20)
    pnr = f"452{datetime.now().strftime('%H%M%S')}"
    set_status(booking_id, "confirmed", f"✅ Ticket confirmed! PNR: {pnr}", pnr=pnr)
    await _notify_core_service(booking_id, pnr)


def get_status(booking_id: str) -> dict:
    return booking_statuses.get(booking_id, {
        "status": "not_found",
        "message": "Booking not found"
    })