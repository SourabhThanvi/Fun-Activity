"""
Buzz Scoring Engine for Events.

BUZZ FORMULA:
  Google Trends (7-day regional)                    × 0.30
  News Coverage (article count + source quality)    × 0.30
  Reddit Buzz (posts + upvotes + comments)          × 0.25
  Time Proximity                                    × 0.15

When a source returns no data, its weight is redistributed
proportionally to sources that DID return data.
"""

import asyncio
from datetime import datetime, timezone
from dateutil import parser as dateparser
from config import (
    BUZZ_WEIGHTS,
    NEWS_MAX_ARTICLES,
    REDDIT_MAX_POSTS,
    REDDIT_MAX_UPVOTES,
    REDDIT_MAX_COMMENTS,
)
from data_sources.serpapi_client import search_news
from data_sources.reddit_client import search_reddit
from data_sources.google_trends import fetch_trends


async def compute_buzz_score(event_name: str, city: str, event_date: str = "") -> dict:
    """
    Compute comprehensive buzz score for an event.
    
    Args:
        event_name: Name of the event
        city: City name
        event_date: Optional date string for time proximity calculation
    
    Returns:
        {
            "buzz_score": 0-100,
            "buzz_level": "High" | "Medium" | "Low" | "Minimal",
            "breakdown": { source: score },
            "evidence": { source: details },
            "sources_available": int,
        }
    """
    # Fetch all sources concurrently
    trends_task = fetch_trends(f"{event_name} {city}")
    news_task = search_news(event_name, city)
    reddit_task = search_reddit(event_name, city)
    
    trends_data, news_data, reddit_data = await asyncio.gather(
        trends_task, news_task, reddit_task,
        return_exceptions=True,
    )
    
    # Handle exceptions from gather
    if isinstance(trends_data, Exception):
        trends_data = {"interest_score": 0, "error": str(trends_data)}
    if isinstance(news_data, Exception):
        news_data = []
    if isinstance(reddit_data, Exception):
        reddit_data = {"total_posts": 0}
    
    # Score each source (0-100)
    scores = {}
    evidence = {}
    
    # --- Google Trends ---
    scores["google_trends"] = _score_trends(trends_data)
    evidence["google_trends"] = _evidence_trends(trends_data)
    
    # --- News Coverage ---
    scores["news_coverage"] = _score_news(news_data)
    evidence["news_coverage"] = _evidence_news(news_data)
    
    # --- Reddit ---
    scores["reddit_buzz"] = _score_reddit(reddit_data)
    evidence["reddit_buzz"] = _evidence_reddit(reddit_data)
    
    # --- Time Proximity ---
    scores["time_proximity"] = _score_time_proximity(event_date)
    evidence["time_proximity"] = _evidence_time_proximity(event_date)
    
    # --- Compute weighted total with fallback redistribution ---
    buzz_score = _weighted_total(scores)
    
    # Determine buzz level
    if buzz_score >= 70:
        buzz_level = "High"
    elif buzz_score >= 45:
        buzz_level = "Medium"
    elif buzz_score >= 20:
        buzz_level = "Low"
    else:
        buzz_level = "Minimal"
    
    sources_with_data = sum(
        1 for k, v in scores.items()
        if v > 0 and k != "time_proximity"
    )

    # If no real data sources returned data, override buzz level to Minimal
    # (prevents time_proximity alone from inflating score to "Medium")
    if sources_with_data == 0:
        buzz_level = "Minimal"
        buzz_score = 0.0

    return {
        "buzz_score": round(buzz_score, 2),
        "buzz_level": buzz_level,
        "breakdown": {k: round(v, 2) for k, v in scores.items()},
        "evidence": evidence,
        "sources_available": sources_with_data,
    }


def _weighted_total(scores: dict) -> float:
    """
    Compute weighted total with fallback redistribution.
    If a source scores 0 (no data), redistribute its weight proportionally.
    """
    active_sources = {k: v for k, v in scores.items() if v > 0}
    inactive_weight = sum(
        BUZZ_WEIGHTS[k] for k in scores if scores[k] == 0 and k in BUZZ_WEIGHTS
    )
    
    if not active_sources:
        return 0
    
    total_active_weight = sum(BUZZ_WEIGHTS.get(k, 0) for k in active_sources)
    
    if total_active_weight == 0:
        return 0
    
    # Redistribute inactive weight proportionally
    total = 0
    for source, score in active_sources.items():
        base_weight = BUZZ_WEIGHTS.get(source, 0)
        if total_active_weight > 0:
            bonus_weight = inactive_weight * (base_weight / total_active_weight)
        else:
            bonus_weight = 0
        total += score * (base_weight + bonus_weight)
    
    return min(total, 100)


# ─── Scoring Functions ───

def _score_trends(data: dict) -> float:
    """Score Google Trends data (0-100)."""
    if "error" in data or not data:
        return 0
    return min(data.get("interest_score", 0), 100)


def _score_news(articles: list) -> float:
    """Score based on news article count. 0 articles = 0, 20+ = 100."""
    count = len(articles) if articles else 0
    return min((count / NEWS_MAX_ARTICLES) * 100, 100)


def _score_reddit(data: dict) -> float:
    """
    Score Reddit buzz from posts, upvotes, and comments.
    35% posts, 30% upvotes, 25% comments, 10% recency.
    """
    if not data or data.get("total_posts", 0) == 0:
        return 0
    
    posts_score = min((data.get("total_posts", 0) / REDDIT_MAX_POSTS) * 100, 100)
    upvotes_score = min((data.get("total_upvotes", 0) / REDDIT_MAX_UPVOTES) * 100, 100)
    comments_score = min((data.get("total_comments", 0) / REDDIT_MAX_COMMENTS) * 100, 100)
    
    # Recency: post within 1 day = 100, 7 days = 70, 14 = 40, 30 = 20
    recent_age = data.get("most_recent_post_age_days")
    if recent_age is not None:
        if recent_age <= 1:
            recency = 100
        elif recent_age <= 7:
            recency = 70
        elif recent_age <= 14:
            recency = 40
        else:
            recency = 20
    else:
        recency = 0
    
    return (
        posts_score * 0.35
        + upvotes_score * 0.30
        + comments_score * 0.25
        + recency * 0.10
    )


def _score_time_proximity(event_date: str) -> float:
    """
    Score based on how soon the event is.
    Tomorrow = 100, 3 days = 90, 7 days = 70, 14 = 50, 30 = 30, 60+ = 10.
    """
    if not event_date:
        return 50  # Unknown date, give neutral score
    
    try:
        parsed = dateparser.parse(event_date, fuzzy=True)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        
        now = datetime.now(timezone.utc)
        days_until = (parsed - now).days
        
        if days_until < 0:
            return 20  # Already happened, low proximity
        elif days_until <= 1:
            return 100
        elif days_until <= 3:
            return 90
        elif days_until <= 7:
            return 70
        elif days_until <= 14:
            return 50
        elif days_until <= 30:
            return 30
        else:
            return 10
    except Exception:
        return 50  # Can't parse date, neutral


# ─── Evidence Functions (for transparency) ───

def _evidence_trends(data: dict) -> dict:
    if "error" in data:
        return {"status": "unavailable", "reason": data["error"]}
    return {
        "interest_score": data.get("interest_score", 0),
        "is_trending": data.get("is_trending", False),
        "related_queries": data.get("related_queries", []),
    }


def _evidence_news(articles: list) -> dict:
    count = len(articles) if articles else 0
    sources = [a.get("source", "Unknown") for a in (articles or [])[:5]]
    return {
        "article_count": count,
        "top_sources": sources,
        "summary": f"{count} news articles found in recent coverage",
    }


def _evidence_reddit(data: dict) -> dict:
    if not data or data.get("total_posts", 0) == 0:
        return {"total_posts": 0, "status": "no Reddit discussion found"}
    return {
        "total_posts": data.get("total_posts", 0),
        "total_upvotes": data.get("total_upvotes", 0),
        "total_comments": data.get("total_comments", 0),
        "subreddits": data.get("subreddits_found", []),
        "most_recent_days_ago": data.get("most_recent_post_age_days"),
        "summary": (
            f"{data['total_posts']} Reddit threads, "
            f"{data['total_upvotes']} upvotes, "
            f"{data['total_comments']} comments"
        ),
    }


def _evidence_time_proximity(event_date: str) -> dict:
    if not event_date:
        return {"status": "event date unknown"}
    try:
        parsed = dateparser.parse(event_date, fuzzy=True)
        now = datetime.now(timezone.utc)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        days_until = (parsed - now).days
        return {
            "event_date": event_date,
            "days_until": days_until,
            "summary": f"Event in {days_until} days" if days_until > 0 else "Event has passed",
        }
    except Exception:
        return {"status": "could not parse event date"}