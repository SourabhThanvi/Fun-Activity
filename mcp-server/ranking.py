"""
Ranking Engine for Fun Activity Zones.

RANKING FORMULA:
  Confidence-Weighted Rating (Bayesian)  × 0.50
  Activity Variety Score                 × 0.25
  Category Diversity Bonus               × 0.15
  Photo Count Score                      × 0.10

All scores normalized to 0-100 before weighting.
"""

import math
from config import (
    RANKING_WEIGHTS,
    BAYESIAN_MIN_REVIEWS,
    CATEGORY_MAP,
    DEFAULT_CATEGORY,
)


def rank_fun_zones(places: list[dict]) -> list[dict]:
    """
    Rank a list of places using the weighted scoring formula.
    Returns places sorted by rank score (highest first) with scores attached.
    """
    if not places:
        return []
    
    # Step 1: Compute city average rating (for Bayesian calculation)
    ratings = [p["rating"] for p in places if p.get("rating", 0) > 0]
    city_avg_rating = sum(ratings) / len(ratings) if ratings else 3.5
    
    # Step 2: Compute max photo count for normalization
    photo_counts = [p.get("photos_count", 0) for p in places]
    max_photos = max(photo_counts) if photo_counts else 1
    
    # Step 3: Track category counts for diversity scoring
    category_counts = {}
    
    # Step 4: Score each place
    scored_places = []
    for place in places:
        scores = {}
        
        # --- Bayesian Rating (0-100) ---
        scores["bayesian_rating"] = _bayesian_rating(
            rating=place.get("rating", 0),
            review_count=place.get("review_count", 0),
            city_avg=city_avg_rating,
            min_reviews=BAYESIAN_MIN_REVIEWS,
        )
        
        # --- Activity Variety (0-100) ---
        scores["activity_variety"] = _activity_variety_score(place)
        
        # --- Category Diversity (0-100) ---
        category = _get_category(place)
        place["category"] = category
        category_counts[category] = category_counts.get(category, 0) + 1
        scores["category_diversity"] = _category_diversity_score(
            category, category_counts
        )
        
        # --- Photo Count (0-100) ---
        scores["photo_count"] = _photo_score(
            place.get("photos_count", 0), max_photos
        )
        
        # --- Weighted Total ---
        total = sum(
            scores[key] * RANKING_WEIGHTS[key]
            for key in RANKING_WEIGHTS
        )
        
        # Attach scores and metadata
        place["rank_score"] = round(total, 2)
        place["score_breakdown"] = {k: round(v, 2) for k, v in scores.items()}
        
        scored_places.append(place)
    
    # Step 5: Sort by rank score descending
    scored_places.sort(key=lambda x: x["rank_score"], reverse=True)
    
    # Step 6: Assign rank numbers
    for i, place in enumerate(scored_places):
        place["rank"] = i + 1
    
    return scored_places


def _bayesian_rating(
    rating: float,
    review_count: int,
    city_avg: float,
    min_reviews: int,
) -> float:
    """
    Compute Bayesian average (IMDb-style weighted rating).
    
    Formula: (v / (v + m)) × R + (m / (v + m)) × C
    
    Where:
        R = place's rating
        v = number of reviews
        m = minimum reviews threshold
        C = city average rating
    
    A 4.8★ place with 10 reviews gets pulled toward city average.
    A 4.5★ place with 2000 reviews stays near 4.5.
    """
    if rating <= 0:
        return 0
    
    v = max(review_count, 0)
    m = min_reviews
    R = rating
    C = city_avg
    
    bayesian = (v / (v + m)) * R + (m / (v + m)) * C
    
    # Normalize to 0-100 (ratings are 1-5)
    return ((bayesian - 1) / 4) * 100


def _activity_variety_score(place: dict) -> float:
    """
    Score based on how many different activities/sub-services a place offers.
    
    Sources of variety data:
    - 'types' from Google (e.g., ['amusement_park', 'bowling_alley'])
    - 'extensions' from SerpAPI (e.g., ['Trampoline', 'Laser tag', 'PS5'])
    - 'services' if available
    - Keywords in description/name
    """
    variety_signals = set()
    
    # From Google types
    for t in place.get("types", []):
        t_clean = t.strip().lower()
        if t_clean and t_clean not in ("point_of_interest", "establishment"):
            variety_signals.add(t_clean)
    
    # From extensions (SerpAPI often puts activity types here)
    for ext in place.get("extensions", []):
        if isinstance(ext, str):
            variety_signals.add(ext.strip().lower())
    
    # From services
    for svc in place.get("services", []):
        if isinstance(svc, str):
            variety_signals.add(svc.strip().lower())
    
    # Keyword detection in name + description
    activity_keywords = [
        "trampoline", "bowling", "laser tag", "go kart", "go-kart",
        "paintball", "arcade", "gaming", "ps4", "ps5", "xbox",
        "escape room", "vr", "virtual reality", "zipline", "zip line",
        "rock climbing", "swimming", "pool", "water slide", "bumper car",
        "mini golf", "cricket", "football", "basketball", "skating",
        "ice skating", "roller coaster", "rides", "bumper boat",
    ]
    
    text = f"{place.get('name', '')} {place.get('description', '')}".lower()
    for kw in activity_keywords:
        if kw in text:
            variety_signals.add(kw)
    
    count = len(variety_signals)
    
    # Scoring: 1 activity = 20, 2 = 40, 3 = 60, 4 = 80, 5+ = 100
    if count <= 0:
        return 10  # Base score — we know it's SOME kind of fun zone
    elif count == 1:
        return 25
    elif count == 2:
        return 45
    elif count == 3:
        return 65
    elif count == 4:
        return 80
    else:
        return 100


def _get_category(place: dict) -> str:
    """Map a place to one of our high-level categories."""
    for t in place.get("types", []):
        t_clean = t.strip().lower().replace(" ", "_")
        if t_clean in CATEGORY_MAP:
            return CATEGORY_MAP[t_clean]
    
    for t in place.get("raw_types", []):
        t_clean = t.strip().lower().replace(" ", "_")
        if t_clean in CATEGORY_MAP:
            return CATEGORY_MAP[t_clean]
    
    return DEFAULT_CATEGORY


def _category_diversity_score(category: str, category_counts: dict) -> float:
    """
    Penalize places whose category is already over-represented in results.
    First of a category = 100, second = 80, third = 60, etc.
    """
    count = category_counts.get(category, 1)
    
    if count <= 1:
        return 100
    elif count == 2:
        return 80
    elif count == 3:
        return 60
    elif count == 4:
        return 40
    elif count == 5:
        return 25
    else:
        return 15


def _photo_score(photo_count: int, max_photos: int) -> float:
    """
    Normalize photo count relative to the most-photographed place.
    When no photo data is available (all zeros), give neutral score.
    """
    if max_photos <= 0:
        return 50  # No photo data available — neutral score for everyone
    if photo_count <= 0:
        return 0
    
    log_count = math.log1p(photo_count)
    log_max = math.log1p(max_photos)
    
    return (log_count / log_max) * 100 if log_max > 0 else 50