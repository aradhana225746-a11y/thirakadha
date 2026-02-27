from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

from database import init_db
from routers.auth import router as auth_router
from routers.chat import router as chat_router
from routers.booking import router as booking_router
from routers.notifications import router as notifications_router
from services.monitoring_service import start_scheduler

app = FastAPI(
    title="Thirakadha - Core Service",
    description="Auth, NLP, Db, Notifications, Scheduling",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(booking_router)
app.include_router(notifications_router)

@app.on_event("startup")
async def startup():
    print("Core Service Running...")
    await init_db()
    print("Database ready.")
    start_scheduler()
    print("Core Service ready on port 8000")

@app.get("/")
async def root():
    return {"service": "Thirakadha Core", "status": "running", "port": 8000}

@app.get("/health")
async def health():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True) 