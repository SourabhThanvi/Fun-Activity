"""
Reddit client for buzz scoring.
Uses Reddit's public JSON API (no auth needed for basic search).
Rate limit: ~60 requests/minute without auth.
"""

import httpx
from datetime import datetime, timedelta, timezone

REDDIT_SEARCH_URL = "https://www.reddit.com/search.json"
REDDIT_USER_AGENT = "CityBuzzTracker/1.0"


async def search_reddit(query: str, city: str, days: int = 30) -> dict:
    """
    Search Reddit for posts about a topic/event in a city.
    
    Returns:
        {
            "posts": [...],
            "total_posts": int,
            "total_upvotes": int,
            "total_comments": int,
            "most_recent_post_age_days": int,
            "subreddits_found": [str],
        }
    """
    headers = {"User-Agent": REDDIT_USER_AGENT}
    
    # Try multiple search queries for better coverage
    search_queries = [
        f"{query} {city}",
        f"{query}",
    ]
    
    all_posts = []
    seen_ids = set()
    
    async with httpx.AsyncClient(timeout=15) as client:
        for q in search_queries:
            try:
                resp = await client.get(
                    REDDIT_SEARCH_URL,
                    params={
                        "q": q,
                        "sort": "relevance",
                        "t": "month",  # Last month
                        "limit": 25,
                        "type": "link",
                    },
                    headers=headers,
                )
                
                if resp.status_code == 429:
                    # Rate limited — return what we have
                    break
                
                resp.raise_for_status()
                data = resp.json()
                
                posts = data.get("data", {}).get("children", [])
                
                for post in posts:
                    p = post.get("data", {})
                    post_id = p.get("id", "")
                    
                    if post_id in seen_ids:
                        continue
                    seen_ids.add(post_id)
                    
                    # Filter by date
                    created_utc = p.get("created_utc", 0)
                    post_date = datetime.fromtimestamp(created_utc, tz=timezone.utc)
                    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
                    
                    if post_date < cutoff:
                        continue
                    
                    all_posts.append({
                        "title": p.get("title", ""),
                        "subreddit": p.get("subreddit", ""),
                        "upvotes": p.get("ups", 0),
                        "comments": p.get("num_comments", 0),
                        "created_utc": created_utc,
                        "url": f"https://reddit.com{p.get('permalink', '')}",
                        "age_days": (datetime.now(timezone.utc) - post_date).days,
                    })
                
            except httpx.TimeoutException:
                continue
            except httpx.HTTPStatusError:
                continue
            except Exception:
                continue
    
    if not all_posts:
        return {
            "posts": [],
            "total_posts": 0,
            "total_upvotes": 0,
            "total_comments": 0,
            "most_recent_post_age_days": None,
            "subreddits_found": [],
        }
    
    total_upvotes = sum(p["upvotes"] for p in all_posts)
    total_comments = sum(p["comments"] for p in all_posts)
    subreddits = list(set(p["subreddit"] for p in all_posts))
    most_recent_age = min(p["age_days"] for p in all_posts)
    
    return {
        "posts": sorted(all_posts, key=lambda x: x["upvotes"], reverse=True),
        "total_posts": len(all_posts),
        "total_upvotes": total_upvotes,
        "total_comments": total_comments,
        "most_recent_post_age_days": most_recent_age,
        "subreddits_found": subreddits,
    }