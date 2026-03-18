"""
City Fun Zones & Buzz Tracker — MCP Server

Tools:
  1. get_fun_zones(city, limit) — Ranked fun activity zones with Bayesian scoring
  2. get_upcoming_events(city) — Events from PredictHQ + SerpAPI Google Events
  3. get_buzz_score(event_name, city, event_date) — Multi-source buzz analysis

Run: python server.py
Transport: stdio (for Claude Desktop)
"""

import json
import asyncio
from difflib import SequenceMatcher
from mcp.server.fastmcp import FastMCP
from data_sources.serpapi_client import search_fun_zones, search_events
from data_sources.predicthq_client import search_events_predicthq
from ranking import rank_fun_zones
from buzz import compute_buzz_score
from cache import cache

# ─── Initialize MCP Server ───
mcp = FastMCP("city-buzz-tracker")


# ─── Tool 1: Get Fun Zones ───
@mcp.tool()
async def get_fun_zones(city: str, limit: int = 20) -> str:
    """
    Find and rank fun activity zones in a city.
    
    Returns ranked list of entertainment venues, adventure parks,
    gaming zones, and activity centers — scored using Bayesian rating,
    activity variety, category diversity, and photo presence.
    
    Args:
        city: City name (e.g., "Jaipur", "Mumbai", "Delhi")
        limit: Maximum number of results (default: 20, max: 50)
    """
    limit = max(1, min(limit, 50))
    
    cache_key = f"fun_zones:{city.lower()}:{limit}"
    cached = cache.get(cache_key)
    if cached:
        return cached
    
    places = await search_fun_zones(city, limit=limit)
    
    if not places:
        return json.dumps({
            "city": city,
            "status": "no_results",
            "message": f"Could not find fun activity zones in {city}. This might be due to API limits or the city not having enough listed venues.",
            "results": [],
        }, indent=2)
    
    ranked = rank_fun_zones(places)
    
    output = {
        "city": city,
        "total_found": len(ranked),
        "ranking_method": "Bayesian Rating (50%) + Activity Variety (25%) + Category Diversity (15%) + Photo Score (10%)",
        "results": [
            {
                "rank": p["rank"],
                "name": p["name"],
                "rank_score": p["rank_score"],
                "rating": p["rating"],
                "review_count": p["review_count"],
                "category": p.get("category", ""),
                "address": p["address"],
                "price_label": p.get("price_label", "Not Available"),
                "photos_count": p.get("photos_count", 0),
                "score_breakdown": p.get("score_breakdown", {}),
                "website": p.get("website", ""),
                "phone": p.get("phone", ""),
                "hours": p.get("hours", ""),
            }
            for p in ranked
        ],
    }
    
    result = json.dumps(output, indent=2, ensure_ascii=False)
    cache.set(cache_key, result)
    return result


# ─── Tool 2: Get Upcoming Events (PredictHQ + SerpAPI) ───
@mcp.tool()
async def get_upcoming_events(city: str) -> str:
    """
    Find upcoming events in a city using multiple sources.
    
    Primary source: PredictHQ (includes rank, predicted attendance, categories).
    Secondary source: SerpAPI Google Events (broader coverage).
    Results are merged and deduplicated.
    
    PredictHQ events include built-in intelligence:
    - phq_rank (0-100): global event importance
    - local_rank (0-100): importance relative to this area
    - phq_attendance: predicted number of attendees
    
    Use get_buzz_score() on individual events to get detailed buzz analysis.
    
    Args:
        city: City name (e.g., "Jaipur", "Mumbai", "Delhi")
    """
    cache_key = f"events:{city.lower()}"
    cached = cache.get(cache_key)
    if cached:
        return cached
    
    # Fetch from both sources concurrently
    phq_task = search_events_predicthq(city)
    serp_task = search_events(city)
    
    phq_events, serp_events = await asyncio.gather(
        phq_task, serp_task,
        return_exceptions=True,
    )
    
    if isinstance(phq_events, Exception):
        phq_events = []
    if isinstance(serp_events, Exception):
        serp_events = []
    
    # Normalize SerpAPI events to common format
    serp_normalized = [
        {
            "title": e.get("title", "Unknown Event"),
            "description": e.get("description", ""),
            "category": "",
            "labels": [],
            "date": e.get("date", e.get("when", "")),
            "end_date": "",
            "predicted_end": "",
            "venue": e.get("venue", ""),
            "address": e.get("address", ""),
            "phq_rank": None,
            "local_rank": None,
            "phq_attendance": None,
            "source": "google_events",
            "link": e.get("link", ""),
            "thumbnail": e.get("thumbnail", ""),
        }
        for e in serp_events
    ]
    
    # Merge: PredictHQ first (richer data), then add unique SerpAPI events
    merged = list(phq_events)
    phq_titles = [e["title"].lower().strip() for e in phq_events]
    
    for se in serp_normalized:
        is_duplicate = False
        se_title = se["title"].lower().strip()
        for pt in phq_titles:
            similarity = SequenceMatcher(None, se_title, pt).ratio()
            if similarity > 0.6:
                is_duplicate = True
                break
        if not is_duplicate:
            merged.append(se)
    
    if not merged:
        return json.dumps({
            "city": city,
            "status": "no_results",
            "message": f"No upcoming events found for {city}. Try a larger city or check back later.",
            "events": [],
            "sources_checked": ["predicthq", "google_events"],
        }, indent=2)
    
    # Sort: PredictHQ ranked events first, then Google Events
    merged.sort(key=lambda x: (x.get("phq_rank") or 0), reverse=True)
    
    phq_count = sum(1 for e in merged if e.get("source") == "predicthq")
    serp_count = sum(1 for e in merged if e.get("source") == "google_events")
    
    output = {
        "city": city,
        "total_events": len(merged),
        "sources": {
            "predicthq": f"{phq_count} events (includes rank & attendance predictions)",
            "google_events": f"{serp_count} events",
        },
        "note": "Use get_buzz_score(event_name, city, event_date) to analyze buzz for any event.",
        "events": merged,
    }
    
    result = json.dumps(output, indent=2, ensure_ascii=False)
    cache.set(cache_key, result)
    return result


# ─── Tool 3: Get Buzz Score ───
@mcp.tool()
async def get_buzz_score(event_name: str, city: str, event_date: str = "") -> str:
    """
    Analyze the buzz level for an event or topic in a city.
    
    Computes a Buzz Score (0-100) using:
    - Google Trends search interest (30%)
    - News coverage (30%)
    - Reddit discussion and engagement (25%)
    - Time proximity to event (15%)
    
    All data comes from real, verifiable sources. Evidence is provided
    alongside the score for transparency.
    
    Args:
        event_name: Name of the event or topic (e.g., "Jaipur Literature Festival")
        city: City name (e.g., "Jaipur")
        event_date: Optional event date for proximity scoring (e.g., "2026-04-15")
    """
    cache_key = f"buzz:{event_name.lower()}:{city.lower()}:{event_date}"
    cached = cache.get(cache_key)
    if cached:
        return cached
    
    buzz_data = await compute_buzz_score(event_name, city, event_date)
    
    output = {
        "event": event_name,
        "city": city,
        "buzz_score": buzz_data["buzz_score"],
        "buzz_level": buzz_data["buzz_level"],
        "scoring_method": (
            "Google Trends (30%) + News Coverage (30%) + "
            "Reddit (25%) + Time Proximity (15%)"
        ),
        "score_breakdown": buzz_data["breakdown"],
        "evidence": buzz_data["evidence"],
        "sources_with_data": buzz_data["sources_available"],
        "note": (
            "Buzz score is computed from real data sources. "
            "If some sources returned no data, their weight was "
            "redistributed to active sources."
        ),
    }
    
    result = json.dumps(output, indent=2, ensure_ascii=False)
    cache.set(cache_key, result)
    return result


# ─── Run Server ───
if __name__ == "__main__":
    mcp.run(transport="stdio")