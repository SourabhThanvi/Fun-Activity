"""
PredictHQ client for event discovery.
Free tier: ~1000 events/month.

PredictHQ provides:
- Event search by location/city
- rank (0-100): global importance score
- local_rank (0-100): local importance relative to the area
- phq_attendance: predicted attendance count
- categories: concerts, conferences, sports, festivals, etc.

These are built-in "buzz-like" signals we get for free with every event.

Signup: https://control.predicthq.com/signup
API Token: https://control.predicthq.com/clients
"""

import httpx
from typing import Optional
from datetime import datetime, timedelta, timezone
from config import PREDICTHQ_API_KEY

PREDICTHQ_BASE = "https://api.predicthq.com/v1"

# City to approximate coordinates (expandable)
# PredictHQ searches by lat/lng + radius
CITY_COORDINATES = {
    "jaipur": {"lat": 26.9124, "lng": 75.7873},
    "delhi": {"lat": 28.6139, "lng": 77.2090},
    "mumbai": {"lat": 19.0760, "lng": 72.8777},
    "bangalore": {"lat": 12.9716, "lng": 77.5946},
    "bengaluru": {"lat": 12.9716, "lng": 77.5946},
    "hyderabad": {"lat": 17.3850, "lng": 78.4867},
    "chennai": {"lat": 13.0827, "lng": 80.2707},
    "kolkata": {"lat": 22.5726, "lng": 88.3639},
    "pune": {"lat": 18.5204, "lng": 73.8567},
    "ahmedabad": {"lat": 23.0225, "lng": 72.5714},
    "goa": {"lat": 15.2993, "lng": 74.1240},
    "udaipur": {"lat": 24.5854, "lng": 73.7125},
    "jodhpur": {"lat": 26.2389, "lng": 73.0243},
    "lucknow": {"lat": 26.8467, "lng": 80.9462},
    "chandigarh": {"lat": 30.7333, "lng": 76.7794},
    "kochi": {"lat": 9.9312, "lng": 76.2673},
    "varanasi": {"lat": 25.3176, "lng": 82.9739},
    "indore": {"lat": 22.7196, "lng": 75.8577},
    "nagpur": {"lat": 21.1458, "lng": 79.0882},
    "bhopal": {"lat": 23.2599, "lng": 77.4126},
    # International cities
    "new york": {"lat": 40.7128, "lng": -74.0060},
    "london": {"lat": 51.5074, "lng": -0.1278},
    "dubai": {"lat": 25.2048, "lng": 55.2708},
    "singapore": {"lat": 1.3521, "lng": 103.8198},
    "tokyo": {"lat": 35.6762, "lng": 139.6503},
    "paris": {"lat": 48.8566, "lng": 2.3522},
    "sydney": {"lat": -33.8688, "lng": 151.2093},
}

# Default search radius in km
DEFAULT_RADIUS_KM = 30


async def _predicthq_request(endpoint: str, params: dict) -> dict:
    """Make a PredictHQ API request."""
    if not PREDICTHQ_API_KEY:
        return {"error": "PREDICTHQ_API_KEY not set in environment variables"}
    
    headers = {
        "Authorization": f"Bearer {PREDICTHQ_API_KEY}",
        "Accept": "application/json",
    }
    
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            resp = await client.get(
                f"{PREDICTHQ_BASE}{endpoint}",
                params=params,
                headers=headers,
            )
            resp.raise_for_status()
            return resp.json()
        except httpx.TimeoutException:
            return {"error": "PredictHQ request timed out"}
        except httpx.HTTPStatusError as e:
            return {"error": f"PredictHQ HTTP error: {e.response.status_code}"}
        except Exception as e:
            return {"error": f"PredictHQ error: {str(e)}"}


async def search_events_predicthq(city: str, days_ahead: int = 60, limit: int = 20) -> list[dict]:
    """
    Search for upcoming events in a city using PredictHQ.
    
    Args:
        city: City name
        days_ahead: How many days ahead to search (default: 60)
        limit: Max events to return
    
    Returns:
        List of events with rank, attendance, and category data.
    """
    coords = _get_city_coords(city)
    
    now = datetime.now(timezone.utc)
    future = now + timedelta(days=days_ahead)
    
    params = {
        "active.gte": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "active.lte": future.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "limit": limit,
        "sort": "-rank",  # Highest ranked first
        # Exclude low-importance events
        "rank.gte": 20,
    }
    
    if coords:
        # Search within radius of city center
        params["within"] = f"{DEFAULT_RADIUS_KM}km@{coords['lat']},{coords['lng']}"
    else:
        # Fallback: text search (less precise)
        params["q"] = city
    
    # Exclude some noise categories
    params["category"] = (
        "concerts,conferences,expos,festivals,performing-arts,"
        "community,sports,academic,food-beverage"
    )
    
    data = await _predicthq_request("/events/", params)
    
    if "error" in data:
        return []
    
    results = data.get("results", [])
    
    return [
        {
            "title": e.get("title", "Unknown Event"),
            "description": e.get("description", ""),
            "category": e.get("category", ""),
            "labels": [lbl.get("label", "") for lbl in e.get("phq_labels", [])],
            "date": e.get("start_local", e.get("start", "")),
            "end_date": e.get("end_local", e.get("end", "")),
            "predicted_end": e.get("predicted_end_local", ""),
            # Venue info from entities
            "venue": _extract_venue(e.get("entities", [])),
            "address": (
                _extract_address(e.get("entities", []))
                or (e.get("geo") or {}).get("address", {}).get("formatted_address", "")
            ),
            # Built-in intelligence signals
            "phq_rank": e.get("rank", 0),           # Global importance (0-100)
            "local_rank": e.get("local_rank", 0),    # Local importance (0-100)
            "phq_attendance": e.get("phq_attendance", 0),  # Predicted attendance
            # Source
            "source": "predicthq",
            "predicthq_id": e.get("id", ""),
        }
        for e in results
    ]


def _get_city_coords(city: str) -> Optional[dict]:
    """Get coordinates for a city name."""
    city_lower = city.strip().lower()
    
    # Direct match
    if city_lower in CITY_COORDINATES:
        return CITY_COORDINATES[city_lower]
    
    # Partial match
    for key, coords in CITY_COORDINATES.items():
        if key in city_lower or city_lower in key:
            return coords
    
    return None


def _extract_venue(entities: list) -> str:
    """Extract venue name from PredictHQ entities."""
    for e in entities:
        if e.get("type") == "venue":
            return e.get("name", "")
    return ""


def _extract_address(entities: list) -> str:
    """Extract venue address from PredictHQ entities."""
    for e in entities:
        if e.get("type") == "venue":
            return e.get("formatted_address", "")
    return ""