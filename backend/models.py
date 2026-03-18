"""
Database tables.

Tables:
    cities      — City master list
    fun_zones   — Fun activity zones with rank scores
    events      — Upcoming events from APIs
    buzz_scores — Buzz analysis results (separate so we can track history)
    users       — Auth (added later)
"""

from datetime import datetime, timezone
from sqlalchemy import String, Integer, Float, Boolean, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database import Base


def now_utc():
    return datetime.now(timezone.utc)


# ─────────────────────────────────────────────
# Cities
# ─────────────────────────────────────────────
class City(Base):
    __tablename__ = "cities"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    state: Mapped[str] = mapped_column(String(100), default="")
    country: Mapped[str] = mapped_column(String(100), default="India")
    latitude: Mapped[float] = mapped_column(Float, nullable=True)
    longitude: Mapped[float] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    fun_zones = relationship("FunZone", back_populates="city")
    events = relationship("Event", back_populates="city")


# ─────────────────────────────────────────────
# Fun Zones
# ─────────────────────────────────────────────
class FunZone(Base):
    __tablename__ = "fun_zones"

    id: Mapped[int] = mapped_column(primary_key=True)
    city_id: Mapped[int] = mapped_column(ForeignKey("cities.id"))
    name: Mapped[str] = mapped_column(String(255))
    rating: Mapped[float] = mapped_column(Float, default=0.0)
    review_count: Mapped[int] = mapped_column(Integer, default=0)
    rank_score: Mapped[float] = mapped_column(Float, default=0.0)
    rank_position: Mapped[int] = mapped_column(Integer, default=0)
    category: Mapped[str] = mapped_column(String(100), default="")
    address: Mapped[str] = mapped_column(Text, default="")
    price_label: Mapped[str] = mapped_column(String(50), default="Not Available")
    photos_count: Mapped[int] = mapped_column(Integer, default=0)
    website: Mapped[str] = mapped_column(Text, default="")
    phone: Mapped[str] = mapped_column(String(50), default="")
    place_id: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    city = relationship("City", back_populates="fun_zones")


# ─────────────────────────────────────────────
# Events
# ─────────────────────────────────────────────
class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(primary_key=True)
    city_id: Mapped[int] = mapped_column(ForeignKey("cities.id"))
    title: Mapped[str] = mapped_column(String(500))
    description: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(String(100), default="")
    event_date: Mapped[str] = mapped_column(String(100), default="")
    end_date: Mapped[str] = mapped_column(String(100), default="")
    venue: Mapped[str] = mapped_column(String(255), default="")
    address: Mapped[str] = mapped_column(Text, default="")
    phq_rank: Mapped[int] = mapped_column(Integer, nullable=True)
    local_rank: Mapped[int] = mapped_column(Integer, nullable=True)
    phq_attendance: Mapped[int] = mapped_column(Integer, nullable=True)
    source: Mapped[str] = mapped_column(String(50), default="")
    link: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    city = relationship("City", back_populates="events")
    buzz_scores = relationship("BuzzScore", back_populates="event")


# ─────────────────────────────────────────────
# Buzz Scores (separate table = history tracking)
# ─────────────────────────────────────────────
class BuzzScore(Base):
    __tablename__ = "buzz_scores"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"))
    buzz_score: Mapped[float] = mapped_column(Float, default=0.0)
    buzz_level: Mapped[str] = mapped_column(String(20), default="Minimal")
    breakdown: Mapped[dict] = mapped_column(JSON, default=dict)
    evidence: Mapped[dict] = mapped_column(JSON, default=dict)
    sources_available: Mapped[int] = mapped_column(Integer, default=0)
    scored_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    event = relationship("Event", back_populates="buzz_scores")


# ─────────────────────────────────────────────
# Users (auth — built last)
# ─────────────────────────────────────────────
class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(100), default="")
    role: Mapped[str] = mapped_column(String(20), default="user")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)