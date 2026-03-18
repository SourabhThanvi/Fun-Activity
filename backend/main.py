"""
FUN-ACTIVITY Backend.

Run:   cd backend && uvicorn main:app --reload
Docs:  http://localhost:8000/docs
"""

import sys
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, func

# Add mcp-server to path
MCP_DIR = str(Path(__file__).resolve().parent.parent / "mcp-server")
if MCP_DIR not in sys.path:
    sys.path.insert(0, MCP_DIR)

from database import engine, Base, async_session
from models import City, FunZone, Event, BuzzScore

from routes.city_routes import router as city_router
from routes.funzone_routes import router as funzone_router
from routes.event_routes import router as event_router
from routes.buzz_routes import router as buzz_router


# ─── Startup / Shutdown ───
@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Database tables ready")
    yield
    await engine.dispose()


# ─── Create App ───
app = FastAPI(
    title="FUN-ACTIVITY API",
    description="Fun zones, events, and buzz analysis for any city.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Mount Routes ───
app.include_router(city_router)
app.include_router(funzone_router)
app.include_router(event_router)
app.include_router(buzz_router)


@app.get("/")
async def root():
    return {"name": "FUN-ACTIVITY API", "docs": "/docs"}


@app.get("/dashboard")
async def dashboard():
    async with async_session() as db:
        cities = (await db.execute(select(func.count(City.id)))).scalar() or 0
        zones = (await db.execute(select(func.count(FunZone.id)))).scalar() or 0
        events = (await db.execute(select(func.count(Event.id)))).scalar() or 0
        buzz = (await db.execute(select(func.count(BuzzScore.id)))).scalar() or 0

    return {
        "total_cities": cities,
        "total_fun_zones": zones,
        "total_events": events,
        "total_buzz_scores": buzz,
    }


@app.get("/health")
async def health():
    return {"status": "ok"}