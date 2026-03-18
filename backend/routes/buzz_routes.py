from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from database import get_db
from models import BuzzScore, Event, City
from schemas import BuzzOut, BuzzIn
from services.mcp_sync import sync_buzz

router = APIRouter(prefix="/buzz", tags=["Buzz Scores"])


@router.post("/", response_model=BuzzOut)
async def get_buzz(data: BuzzIn, db: AsyncSession = Depends(get_db)):
    """DB first, compute if empty."""

    city_row = await db.execute(
        select(City).where(func.lower(City.name) == data.city_name.strip().lower())
    )
    city = city_row.scalar_one_or_none()

    if city:
        # Partial match — picks the most important matching event
        event_row = await db.execute(
            select(Event)
            .where(Event.city_id == city.id, Event.title.ilike(f"%{data.event_name.strip()}%"))
            .order_by(Event.phq_rank.desc().nullslast())
            .limit(1)
        )
        event = event_row.scalar_one_or_none()

        if event:
            buzz_row = await db.execute(
                select(BuzzScore).where(BuzzScore.event_id == event.id).order_by(BuzzScore.scored_at.desc()).limit(1)
            )
            existing = buzz_row.scalar_one_or_none()
            if existing:
                return existing

    try:
        return await sync_buzz(db, data.event_name, data.city_name, data.event_date)
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Failed to compute buzz score for '{data.event_name}': {str(e)}",
        )


@router.get("/event/{event_id}", response_model=list[BuzzOut])
async def buzz_history(event_id: int, db: AsyncSession = Depends(get_db)):
    """All buzz scores for an event."""
    result = await db.execute(
        select(BuzzScore).where(BuzzScore.event_id == event_id).order_by(BuzzScore.scored_at.desc())
    )
    return result.scalars().all()