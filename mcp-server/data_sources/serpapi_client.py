"""
SerpAPI client for fetching places, news, and events.
Handles all SerpAPI interactions with error handling and rate awareness.
"""

import httpx
from config import SERPAPI_KEY, FUN_ZONE_QUERIES

SERPAPI_BASE = "https://serpapi.com/search.json"


async def _serpapi_request(params: dict) -> dict:
    """Make a single SerpAPI request with error handling."""
    if not SERPAPI_KEY:
        return {"error": "SERPAPI_API_KEY not set in environment variables"}
    
    params["api_key"] = SERPAPI_KEY
    
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            resp = await client.get(SERPAPI_BASE, params=params)
            resp.raise_for_status()
            return resp.json()
        except httpx.TimeoutException:
            return {"error": "SerpAPI request timed out"}
        except httpx.HTTPStatusError as e:
            return {"error": f"SerpAPI HTTP error: {e.response.status_code}"}
        except Exception as e:
            return {"error": f"SerpAPI error: {str(e)}"}


async def search_fun_zones(city: str, limit: int = 20) -> list[dict]:
    """
    Search for fun activity zones in a city using Google Maps via SerpAPI.
    Combines multiple queries for comprehensive results.
    Returns deduplicated, raw place data.
    """
    all_places = []
    seen_place_ids = set()
    
    # Build queries from config — pick first 3 for API budget
    queries_to_use = [f"{q} in {city}" for q in FUN_ZONE_QUERIES[:3]]
    
    for query in queries_to_use:
        if len(all_places) >= limit:
            break
        
        data = await _serpapi_request({
            "engine": "google_maps",
            "q": query,
            "type": "search",
        })
        
        if "error" in data:
            continue
        
        local_results = data.get("local_results", [])
        
        for place in local_results:
            place_id = place.get("place_id", place.get("title", ""))
            if place_id not in seen_place_ids:
                seen_place_ids.add(place_id)
                all_places.append(_normalize_place(place))
    
    return all_places[:limit]


def _normalize_place(raw: dict) -> dict:
    """Normalize raw SerpAPI place data into our standard format."""
    return {
        "name": raw.get("title", "Unknown"),
        "rating": raw.get("rating", 0),
        "review_count": raw.get("reviews", 0),
        "address": raw.get("address", ""),
        "types": raw.get("type", "").split(",") if raw.get("type") else [],
        "description": raw.get("description", ""),
        "price_level": raw.get("price", ""),
        "thumbnail": raw.get("thumbnail", ""),
        "photos_count": raw.get("photos_count", 0),
        "gps_coordinates": raw.get("gps_coordinates", {}),
        "place_id": raw.get("place_id", ""),
        "hours": raw.get("hours", ""),
        "phone": raw.get("phone", ""),
        "website": raw.get("website", ""),
        # Raw types/categories from Google
        "raw_types": raw.get("types", []),
        # Extract sub-services/activities if available
        "services": raw.get("services", []),
        "extensions": raw.get("extensions", []),
    }


async def search_events(city: str) -> list[dict]:
    """
    Search for upcoming events in a city via SerpAPI Google Events.
    """
    data = await _serpapi_request({
        "engine": "google_events",
        "q": f"upcoming events in {city}",
    })
    
    if "error" in data:
        return []
    
    events = data.get("events_results", [])
    
    return [
        {
            "title": e.get("title", "Unknown Event"),
            "date": e.get("date", {}).get("start_date", ""),
            "when": e.get("date", {}).get("when", ""),
            "address": ", ".join(e.get("address", [])),
            "venue": e.get("venue", {}).get("name", ""),
            "link": e.get("link", ""),
            "description": e.get("description", ""),
            "thumbnail": e.get("thumbnail", ""),
            "ticket_info": e.get("ticket_info", []),
        }
        for e in events
    ]


async def search_news(query: str, city: str) -> list[dict]:
    """
    Search recent news articles about a topic in a city.
    Returns article count and basic info.
    """
    data = await _serpapi_request({
        "engine": "google",
        "q": f"{query} {city}",
        "tbm": "nws",
        "num": 20,
    })
    
    if "error" in data:
        return []
    
    articles = data.get("news_results", [])
    
    return [
        {
            "title": a.get("title", ""),
            "source": a.get("source", {}).get("name", "") if isinstance(a.get("source"), dict) else a.get("source", ""),
            "date": a.get("date", ""),
            "snippet": a.get("snippet", ""),
            "link": a.get("link", ""),
        }
        for a in articles
    ]