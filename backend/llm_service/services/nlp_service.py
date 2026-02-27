import httpx
import json
import os

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL   = os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.1-8b-instruct:free")
OPENROUTER_URL     = "https://openrouter.ai/api/v1/chat/completions"

SYSTEM_PROMPT = """You are TripMind, an AI travel assistant for India.
Help users plan and book train/bus trips from a single message.

Always respond ONLY with valid JSON (no markdown, no extra text):
{
  "destination": "city or null",
  "origin": "city or null",
  "date": "DD MMM YYYY or null",
  "purpose": "reason or null",
  "venue": "specific venue or null",
  "travel_class": "Sleeper/AC/2AC/3AC or null",
  "missing_info": [],
  "followup_question": "question if info missing, else null",
  "ready_to_plan": true/false,
  "ready_to_book": false,
  "intent": "plan/book/alert/query"
}

Rules:
- destination + origin + date all required before ready_to_plan = true
- Understand Indian context: "Kazhakootam" = near Trivandrum/Thiruvananthapuram
- Be friendly and brief in followup_question
- Never include markdown or extra explanation, JSON only
"""

# Per-session conversation memory
session_history: dict = {}


async def process_message(message: str, session_id: str) -> dict:
    """Send message to OpenRouter, get structured travel intent back"""

    if session_id not in session_history:
        session_history[session_id] = []

    session_history[session_id].append({"role": "user", "content": message})

    # Keep last 10 messages for context
    history = session_history[session_id][-10:]

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                OPENROUTER_URL,
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "HTTP-Referer": "https://tripmind.app",
                    "X-Title": "TripMind"
                },
                json={
                    "model": OPENROUTER_MODEL,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        *history
                    ],
                    "temperature": 0.2,
                    "max_tokens": 400
                }
            )

            data = response.json()
            raw = data["choices"][0]["message"]["content"].strip()

            # Store assistant reply in history
            session_history[session_id].append({"role": "assistant", "content": raw})

            # Strip markdown code fences if model adds them
            if "```" in raw:
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]

            return json.loads(raw.strip())

    except json.JSONDecodeError:
        return _fallback_response()
    except Exception as e:
        raise Exception(f"OpenRouter error: {e}")


def _fallback_response() -> dict:
    return {
        "destination": None, "origin": None, "date": None,
        "missing_info": ["destination", "origin", "date"],
        "followup_question": "Where are you traveling from and to, and on which date?",
        "ready_to_plan": False, "ready_to_book": False, "intent": "plan"
    }


async def generate_trip_summary(origin: str, destination: str, date: str, purpose: str = None) -> str:
    """Generate a short friendly message to show above train options"""
    purpose_text = f" for {purpose}" if purpose else ""
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                OPENROUTER_URL,
                headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}"},
                json={
                    "model": OPENROUTER_MODEL,
                    "messages": [{
                        "role": "user",
                        "content": f"2-line friendly message confirming trip from {origin} to {destination} on {date}{purpose_text}. Add one travel tip. No formatting."
                    }],
                    "max_tokens": 80
                }
            )
            return response.json()["choices"][0]["message"]["content"]
    except:
        return f"Here are your options from {origin} to {destination} on {date}:"


def get_mock_train_options(origin: str, destination: str, date: str) -> list:
    """Mock train data for hackathon demo — replace with real scraping in production"""
    return [
        {
            "train_name": "Trivandrum Mail",
            "train_number": "12625",
            "departure_time": "07:15 AM",
            "arrival_time": "02:30 PM",
            "duration": "7h 15m",
            "travel_class": "Sleeper",
            "price": 340.0,
            "availability": "AVAILABLE"
        },
        {
            "train_name": "Kerala Express",
            "train_number": "12627",
            "departure_time": "11:30 AM",
            "arrival_time": "07:45 PM",
            "duration": "8h 15m",
            "travel_class": "Sleeper",
            "price": 340.0,
            "availability": "WL/12"
        },
        {
            "train_name": "Rajdhani Express",
            "train_number": "12431",
            "departure_time": "03:45 PM",
            "arrival_time": "09:30 PM",
            "duration": "5h 45m",
            "travel_class": "3AC",
            "price": 890.0,
            "availability": "AVAILABLE"
        }
    ]


def clear_session(session_id: str):
    session_history.pop(session_id, None)