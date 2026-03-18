"""
MCP Sync Service.

Bridge between external APIs and the database.
Fetches data, ranks/scores it, saves to PostgreSQL.
"""

import sys
import asyncio
from pathlib import Path
from difflib import SequenceMatcher
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

# Add mcp-server to path
MCP_DIR = str(Path(__file__).resolve().parent.parent.parent / "mcp-server")
if MCP_DIR not in sys.path:
    sys.path.insert(0, MCP_DIR)

from data_sources.serpapi_client import search_fun_zones as api_fetch_fun_zones
from data_sources.serpapi_client import search_events as api_fetch_events_google
from data_sources.predicthq_client import search_events_predicthq as api_fetch_events_phq
from ranking import rank_fun_zones
from buzz import compute_buzz_score

from models import City, FunZone, Event, BuzzScore


# ─── Helper ───

async def get_or_create_city(db: AsyncSession, city_name: str) -> City:
    """Find city by name, create if missing."""
    result = await db.execute(
        select(City).where(func.lower(City.name) == city_name.strip().lower())
    )
    city = result.scalar_one_or_none()

    if not city:
        city = City(name=city_name.strip().title())
        db.add(city)
        await db.flush()

    return city


# ─── Sync Fun Zones ───

async def sync_fun_zones(db: AsyncSession, city_name: str, limit: int = 20) -> dict:
    """Fetch → Rank → Save fun zones."""
    city = await get_or_create_city(db, city_name)

    # Fetch from API
    raw_places = await api_fetch_fun_zones(city_name, limit=limit)
    if not raw_places:
        return {"city": city_name, "synced_count": 0, "message": "No fun zones found"}

    # Rank them
    ranked = rank_fun_zones(raw_places)

    # Save
    count = 0
    for place in ranked:
        existing = await _find_fun_zone(db, city.id, place["name"])

        if existing:
            existing.rating = place.get("rating", 0)
            existing.review_count = place.get("review_count", 0)
            existing.rank_score = place.get("rank_score", 0)
            existing.rank_position = place.get("rank", 0)
            existing.category = place.get("category", "")
            existing.address = place.get("address", "")
            existing.price_label = place.get("price_label", "Not Available")
            existing.photos_count = place.get("photos_count", 0)
            existing.website = place.get("website", "")
            existing.phone = place.get("phone", "")
        else:
            db.add(FunZone(
                city_id=city.id,
                name=place.get("name", "Unknown"),
                rating=place.get("rating", 0),
                review_count=place.get("review_count", 0),
                rank_score=place.get("rank_score", 0),
                rank_position=place.get("rank", 0),
                category=place.get("category", ""),
                address=place.get("address", ""),
                price_label=place.get("price_label", "Not Available"),
                photos_count=place.get("photos_count", 0),
                website=place.get("website", ""),
                phone=place.get("phone", ""),
                place_id=place.get("place_id", ""),
            ))
        count += 1

    await db.commit()
    return {"city": city_name, "synced_count": count, "message": f"Synced {count} fun zones"}


# ─── Sync Events ───

async def sync_events(db: AsyncSession, city_name: str) -> dict:
    """Fetch from PredictHQ + Google → Merge → Save."""
    city = await get_or_create_city(db, city_name)

    # Fetch from both concurrently
    phq_result, google_result = await asyncio.gather(
        api_fetch_events_phq(city_name),
        api_fetch_events_google(city_name),
        return_exceptions=True,
    )
    phq_events = phq_result if not isinstance(phq_result, Exception) else []
    google_events = google_result if not isinstance(google_result, Exception) else []

    # Merge and deduplicate
    all_events = _merge_events(phq_events, google_events)

    # Save
    count = 0
    for e in all_events:
        existing = await _find_event(db, city.id, e["title"])

        if existing:
            existing.phq_rank = e.get("phq_rank")
            existing.local_rank = e.get("local_rank")
            existing.phq_attendance = e.get("phq_attendance")
        else:
            db.add(Event(
                city_id=city.id,
                title=e["title"],
                description=e.get("description", ""),
                category=e.get("category", ""),
                event_date=e.get("date", ""),
                end_date=e.get("end_date", ""),
                venue=e.get("venue", ""),
                address=e.get("address", ""),
                phq_rank=e.get("phq_rank"),
                local_rank=e.get("local_rank"),
                phq_attendance=e.get("phq_attendance"),
                source=e.get("source", ""),
                link=e.get("link", ""),
            ))
        count += 1

    await db.commit()
    return {"city": city_name, "synced_count": count, "message": f"Synced {count} events"}


# ─── Sync Buzz ───

async def sync_buzz(db: AsyncSession, event_name: str, city_name: str, event_date: str = "") -> BuzzScore:
    """Compute buzz → Save → Return the BuzzScore object."""
    city = await get_or_create_city(db, city_name)

    # Find event or create placeholder
    event = await _find_event(db, city.id, event_name)
    if not event:
        event = Event(city_id=city.id, title=event_name, event_date=event_date, source="manual")
        db.add(event)
        await db.flush()

    # Compute buzz
    result = await compute_buzz_score(event_name, city_name, event_date)

    # Save
    buzz = BuzzScore(
        event_id=event.id,
        buzz_score=result["buzz_score"],
        buzz_level=result["buzz_level"],
        breakdown=result["breakdown"],
        evidence=result["evidence"],
        sources_available=result["sources_available"],
    )
    db.add(buzz)
    await db.commit()
    await db.refresh(buzz)

    return buzz


# ─── Private Helpers ───

async def _find_fun_zone(db: AsyncSession, city_id: int, name: str):
    result = await db.execute(
        select(FunZone).where(FunZone.city_id == city_id, func.lower(FunZone.name) == name.lower())
    )
    return result.scalar_one_or_none()


async def _find_event(db: AsyncSession, city_id: int, title: str):
    result = await db.execute(
        select(Event).where(Event.city_id == city_id, func.lower(Event.title) == title.lower())
    )
    return result.scalar_one_or_none()


def _merge_events(phq_events: list, google_events: list) -> list:
    """Merge PredictHQ + Google Events, skip duplicates."""
    merged = [
        {
            "title": e.get("title", "Unknown"),
            "description": e.get("description", ""),
            "category": e.get("category", ""),
            "date": e.get("date", ""),
            "end_date": e.get("end_date", ""),
            "venue": e.get("venue", ""),
            "address": e.get("address", ""),
            "phq_rank": e.get("phq_rank"),
            "local_rank": e.get("local_rank"),
            "phq_attendance": e.get("phq_attendance"),
            "source": "predicthq",
            "link": "",
        }
        for e in phq_events
    ]

    phq_titles = [e["title"].lower() for e in merged]

    for e in google_events:
        title = e.get("title", "Unknown")
        is_dup = any(SequenceMatcher(None, title.lower(), pt).ratio() > 0.6 for pt in phq_titles)
        if not is_dup:
            merged.append({
                "title": title,
                "description": e.get("description", ""),
                "category": "",
                "date": e.get("date", e.get("when", "")),
                "end_date": "",
                "venue": e.get("venue", ""),
                "address": e.get("address", ""),
                "phq_rank": None,
                "local_rank": None,
                "phq_attendance": None,
                "source": "google_events",
                "link": e.get("link", ""),
            })

    return merged