from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from database import get_db
from models import Event, City
from schemas import EventOut
from services.mcp_sync import sync_events

router = APIRouter(prefix="/events", tags=["Events"])


@router.get("/", response_model=list[EventOut])
async def get_events(city: str = Query(...), db: AsyncSession = Depends(get_db)):
    """DB first, API if empty."""

    city_row = await _find_city(db, city)
    if city_row:
        result = await db.execute(
            select(Event).where(Event.city_id == city_row.id).order_by(Event.phq_rank.desc().nullslast())
        )
        events = result.scalars().all()
        if events:
            return events

    try:
        sync_result = await sync_events(db, city)
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Failed to fetch events for '{city}': {str(e)}",
        )

    if sync_result.get("synced_count", 0) == 0:
        raise HTTPException(
            status_code=404,
            detail=f"No upcoming events found for '{city}'. Try a larger city or check back later.",
        )

    city_row = await _find_city(db, city)
    if not city_row:
        return []

    result = await db.execute(
        select(Event).where(Event.city_id == city_row.id).order_by(Event.phq_rank.desc().nullslast())
    )
    return result.scalars().all()


async def _find_city(db, name):
    result = await db.execute(select(City).where(func.lower(City.name) == name.strip().lower()))
    return result.scalar_one_or_none()