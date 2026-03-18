from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from database import get_db
from models import City
from schemas import CityIn, CityOut

router = APIRouter(prefix="/cities", tags=["Cities"])


@router.get("/", response_model=list[CityOut])
async def list_cities(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(City).order_by(City.name))
    return result.scalars().all()


@router.post("/", response_model=CityOut, status_code=201)
async def create_city(data: CityIn, db: AsyncSession = Depends(get_db)):
    # Check if city already exists
    result = await db.execute(
        select(City).where(func.lower(City.name) == data.name.strip().lower())
    )
    if result.scalar_one_or_none():
        raise HTTPException(409, f"City '{data.name}' already exists")

    city = City(name=data.name.strip().title(), state=data.state, country=data.country)
    db.add(city)
    await db.commit()
    await db.refresh(city)
    return city