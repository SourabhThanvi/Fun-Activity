"""
Simple in-memory cache with TTL.
Prevents redundant API calls within the same session.
"""

import time
from config import CACHE_TTL_SECONDS


class SimpleCache:
    def __init__(self, ttl: int = CACHE_TTL_SECONDS):
        self._store: dict = {}
        self._ttl = ttl
    
    def get(self, key: str):
        """Get cached value if exists and not expired."""
        if key in self._store:
            value, timestamp = self._store[key]
            if time.time() - timestamp < self._ttl:
                return value
            else:
                del self._store[key]
        return None
    
    def set(self, key: str, value):
        """Cache a value with current timestamp."""
        self._store[key] = (value, time.time())
    
    def clear(self):
        """Clear all cache."""
        self._store.clear()
    
    def stats(self) -> dict:
        """Return cache stats."""
        now = time.time()
        active = sum(
            1 for _, (_, ts) in self._store.items()
            if now - ts < self._ttl
        )
        return {
            "total_entries": len(self._store),
            "active_entries": active,
            "ttl_seconds": self._ttl,
        }


# Global cache instance
cache = SimpleCache()