from fastapi import APIRouter, HTTPException, Depends

from database import User
from dependencies import get_current_user
from schemas import ChatMessage, ChatResponse, TripPlan, TrainOption
from services.nlp_service import (
    process_message, get_mock_train_options,
    generate_trip_summary, clear_session, session_history
)

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/", response_model=ChatResponse)
async def chat(body: ChatMessage, user: User = Depends(get_current_user)):
    """
    Main chat endpoint.
    Requires JWT auth — user must be logged in.

    Flow:
      message → NLP intent → followup OR show options → user picks → trigger booking
    """
    try:
        intent = await process_message(body.message, body.session_id)

        # Missing info → ask followup
        if not intent.get("ready_to_plan") and intent.get("followup_question"):
            return ChatResponse(
                reply=intent["followup_question"],
                type="question",
                session_id=body.session_id
            )

        # Alert intent
        if intent.get("intent") == "alert":
            return ChatResponse(
                reply="I'll monitor that train and notify you the moment seats open! 🔔",
                type="alert_set",
                session_id=body.session_id
            )

        # Ready to show train options
        if intent.get("ready_to_plan") and not intent.get("ready_to_book"):
            origin      = intent.get("origin", "")
            destination = intent.get("destination", "")
            date        = intent.get("date", "")
            purpose     = intent.get("purpose")
            venue       = intent.get("venue")

            raw_options  = get_mock_train_options(origin, destination, date)
            train_options = [TrainOption(**o) for o in raw_options]

            trip_plan = TripPlan(
                origin=origin,
                destination=destination,
                travel_date=date,
                purpose=purpose,
                venue=venue,
                train_options=train_options
            )

            summary = await generate_trip_summary(origin, destination, date, purpose)

            return ChatResponse(
                reply=summary,
                type="options",
                trip_plan=trip_plan,
                session_id=body.session_id
            )

        # User confirmed train → ask passenger details
        if intent.get("ready_to_book"):
            return ChatResponse(
                reply="Great! Please confirm your name, age, and gender to proceed with booking.",
                type="need_passenger_details",
                session_id=body.session_id
            )

        # Default greeting
        return ChatResponse(
            reply="Hi! I'm TripMind 🚀 Tell me where you want to go and I'll handle the rest!",
            type="info",
            session_id=body.session_id
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history/{session_id}")
async def get_history(session_id: str, user: User = Depends(get_current_user)):
    return {
        "session_id": session_id,
        "messages": session_history.get(session_id, [])
    }


@router.delete("/session/{session_id}")
async def delete_session(session_id: str, user: User = Depends(get_current_user)):
    clear_session(session_id)
    return {"message": "Session cleared"}