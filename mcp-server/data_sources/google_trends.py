"""
Google Trends client using pytrends.
Completely free, no API key needed.
Returns relative search interest (0-100) for a keyword in a region.
"""

from pytrends.request import TrendReq
import asyncio
from functools import partial


def _fetch_trends_sync(keyword: str, geo: str = "IN", timeframe: str = "now 7-d") -> dict:
    """
    Synchronous Google Trends fetch (pytrends doesn't support async).
    
    Args:
        keyword: Search term (e.g., "Jaipur Literature Festival")
        geo: Country/region code (default: India)
        timeframe: Time range (default: last 7 days)
    
    Returns:
        {
            "interest_score": 0-100,
            "is_trending": bool,
            "trend_data": [...],  # Daily interest values
            "related_queries": [...],
        }
    """
    try:
        pytrends = TrendReq(hl="en-US", tz=0)  # UTC — neutral for multi-city support
        pytrends.build_payload([keyword], cat=0, timeframe=timeframe, geo=geo)
        
        # Get interest over time
        interest_df = pytrends.interest_over_time()
        
        if interest_df.empty:
            return {
                "interest_score": 0,
                "is_trending": False,
                "trend_data": [],
                "related_queries": [],
            }
        
        # Get the interest values for our keyword
        values = interest_df[keyword].tolist()
        current_score = values[-1] if values else 0
        avg_score = sum(values) / len(values) if values else 0
        peak_score = max(values) if values else 0
        
        # Get related queries
        try:
            related = pytrends.related_queries()
            related_top = []
            if keyword in related and related[keyword].get("top") is not None:
                related_top = related[keyword]["top"]["query"].tolist()[:5]
        except Exception:
            related_top = []
        
        return {
            "interest_score": int(peak_score),  # Use peak as our score
            "current_score": int(current_score),
            "average_score": int(avg_score),
            "is_trending": current_score > avg_score,
            "trend_data": values,
            "related_queries": related_top,
        }
    
    except Exception as e:
        return {
            "interest_score": 0,
            "is_trending": False,
            "trend_data": [],
            "related_queries": [],
            "error": str(e),
        }


async def fetch_trends(keyword: str, geo: str = "IN", timeframe: str = "now 7-d") -> dict:
    """Async wrapper for pytrends (runs sync code in executor)."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None,
        partial(_fetch_trends_sync, keyword, geo, timeframe)
    )