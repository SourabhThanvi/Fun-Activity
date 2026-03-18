from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class CityIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    state: str = ""
    country: str = "India"


class CityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    state: str
    country: str
    created_at: datetime


class FunZoneOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    city_id: int
    name: str
    rating: float
    review_count: int
    rank_score: float
    rank_position: int
    category: str
    address: str
    price_label: str
    photos_count: int
    website: str
    phone: str
    created_at: datetime


class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    city_id: int
    title: str
    description: str
    category: str
    event_date: str
    end_date: str
    venue: str
    address: str
    phq_rank: Optional[int]
    local_rank: Optional[int]
    phq_attendance: Optional[int]
    source: str
    link: str
    created_at: datetime


class BuzzIn(BaseModel):
    event_name: str = Field(..., min_length=1)
    city_name: str = Field(..., min_length=1)
    event_date: str = ""


class BuzzOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    event_id: int
    buzz_score: float
    buzz_level: str
    breakdown: dict
    evidence: dict
    sources_available: int
    scored_at: datetime