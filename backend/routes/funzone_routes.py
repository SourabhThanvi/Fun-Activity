from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from database import get_db
from models import FunZone, City
from schemas import FunZoneOut
from services.mcp_sync import sync_fun_zones

router = APIRouter(prefix="/funzones", tags=["Fun Zones"])


@router.get("/", response_model=list[FunZoneOut])
async def get_fun_zones(city: str = Query(...), db: AsyncSession = Depends(get_db)):
    """DB first, API if empty."""

    city_row = await _find_city(db, city)
    if city_row:
        result = await db.execute(
            select(FunZone).where(FunZone.city_id == city_row.id).order_by(FunZone.rank_position)
        )
        zones = result.scalars().all()
        if zones:
            return zones

    try:
        sync_result = await sync_fun_zones(db, city)
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Failed to fetch fun zones for '{city}': {str(e)}",
        )

    if sync_result.get("synced_count", 0) == 0:
        raise HTTPException(
            status_code=404,
            detail=f"No fun activity zones found for '{city}'. Check that the city name is correct.",
        )

    city_row = await _find_city(db, city)
    if not city_row:
        return []

    result = await db.execute(
        select(FunZone).where(FunZone.city_id == city_row.id).order_by(FunZone.rank_position)
    )
    return result.scalars().all()


async def _find_city(db, name):
    result = await db.execute(select(City).where(func.lower(City.name) == name.strip().lower()))
    return result.scalar_one_or_none()