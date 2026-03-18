"""
Configuration for City Fun Zones & Buzz Tracker MCP Server.
All weights, constants, and API keys managed here.
Loads API keys from root-level .env file via python-dotenv.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root (one level up from mcp-server/)
ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")

# ─── API Keys ───
SERPAPI_KEY = os.getenv("SERPAPI_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")  # Reserved for Phase 2: venue discovery
PREDICTHQ_API_KEY = os.getenv("PREDICTHQ_API_KEY", "")

# ─── Ranking Weights (must sum to 1.0) ───
RANKING_WEIGHTS = {
    "bayesian_rating": 0.50,     # Confidence-weighted rating
    "activity_variety": 0.25,    # More sub-activities = higher score
    "category_diversity": 0.15,  # Penalize duplicate categories in results
    "photo_count": 0.10,         # Visual presence / popularity proxy
}

# ─── Bayesian Rating Config ───
BAYESIAN_MIN_REVIEWS = 50  # Minimum reviews to be considered "reliable"

# ─── Buzz Weights (must sum to 1.0) ───
BUZZ_WEIGHTS = {
    "google_trends": 0.30,
    "news_coverage": 0.30,
    "reddit_buzz": 0.25,
    "time_proximity": 0.15,
}

# ─── Fun Zone Categories (for diversity scoring) ───
CATEGORY_MAP = {
    "amusement_park": "Adventure & Theme Parks",
    "aquarium": "Adventure & Theme Parks",
    "zoo": "Adventure & Theme Parks",
    "bowling_alley": "Indoor Entertainment",
    "movie_theater": "Indoor Entertainment",
    "night_club": "Nightlife",
    "bar": "Nightlife",
    "park": "Outdoors & Nature",
    "campground": "Outdoors & Nature",
    "stadium": "Sports & Recreation",
    "gym": "Sports & Recreation",
    "spa": "Wellness",
    "museum": "Culture & Heritage",
    "art_gallery": "Culture & Heritage",
    "tourist_attraction": "Sightseeing",
    "shopping_mall": "Shopping & Markets",
    "restaurant": "Food & Dining",
    "cafe": "Food & Dining",
}

DEFAULT_CATEGORY = "General Entertainment"

# ─── Price Level Labels ───
PRICE_LABELS = {
    0: "Free",
    1: "Affordable",
    2: "Semi-Premium",
    3: "Premium",
    4: "Luxury",
}

# ─── Search Config ───
DEFAULT_FUN_ZONE_LIMIT = 20
MAX_FUN_ZONE_LIMIT = 50

FUN_ZONE_QUERIES = [
    "fun activity zones",
    "adventure parks",
    "entertainment centers",
    "amusement parks",
    "indoor gaming zones",
    "trampoline parks",
    "escape rooms",
    "go karting",
    "paintball",
    "water parks",
    "bowling alleys",
    "laser tag",
]

# ─── Scoring Thresholds ───
NEWS_MAX_ARTICLES = 20
REDDIT_MAX_POSTS = 15
REDDIT_MAX_UPVOTES = 500
REDDIT_MAX_COMMENTS = 200

# ─── Cache Config ───
CACHE_TTL_SECONDS = 6 * 60 * 60  # 6 hours