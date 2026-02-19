"""
DPP Cache Manager

Redis-based caching for Digital Product Passports to minimize database queries
and improve API response times for consumer apps.

Roadmap Phase 4 - Section 2.3: Caching Strategy

Performance targets:
- Cache hit rate: > 80%
- Cache lookup: < 5ms
- API response time: < 500ms (cached), < 2s (uncached)
"""

import redis
import json
import os
from typing import Optional, Dict, Any
from datetime import timedelta

class DPPCache:
    """Redis cache manager for Digital Product Passports"""
    
    def __init__(self, redis_url: str = None):
        """
        Initialize Redis connection.
        
        Args:
            redis_url: Redis connection URL (defaults to env var REDIS_URL)
        """
        self.redis_url = redis_url or os.getenv('REDIS_URL', 'redis://localhost:6379/0')
        self.redis_client = redis.from_url(self.redis_url, decode_responses=True)
        self.default_ttl = 3600  # 1 hour cache for DPPs
        self.version = "v1"  # Cache version for invalidation
        
    def _make_key(self, product_id: str) -> str:
        """Generate cache key for product DPP."""
        return f"dpp:{self.version}:{product_id}"
    
    def get_dpp(self, product_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve DPP from cache.
        
        Args:
            product_id: Product/container identifier
            
        Returns:
            DPP dict if cached, None if cache miss
        """
        try:
            key = self._make_key(product_id)
            cached = self.redis_client.get(key)
            
            if cached:
                return json.loads(cached)
            
            return None
        except Exception as e:
            print(f"Cache read error: {e}")
            return None
    
    def set_dpp(self, product_id: str, dpp: Dict[str, Any], ttl: int = None):
        """
        Cache DPP with TTL.
        
        Args:
            product_id: Product/container identifier
            dpp: DPP dictionary to cache
            ttl: Time-to-live in seconds (default: 1 hour)
        """
        try:
            key = self._make_key(product_id)
            ttl = ttl or self.default_ttl
            
            self.redis_client.setex(
                key,
                ttl,
                json.dumps(dpp)
            )
        except Exception as e:
            print(f"Cache write error: {e}")
    
    def invalidate_dpp(self, product_id: str):
        """
        Invalidate cached DPP (e.g., after aggregation event).
        
        Args:
            product_id: Product/container identifier to invalidate
        """
        try:
            key = self._make_key(product_id)
            self.redis_client.delete(key)
        except Exception as e:
            print(f"Cache invalidation error: {e}")
    
    def invalidate_container_hierarchy(self, container_id: str):
        """
        Invalidate DPP cache for container and all parent containers.
        
        When a new batch is added to a container, all parent containers'
        DPPs become stale and must be invalidated.
        
        Args:
            container_id: Container that was modified
        """
        try:
            from database.connection import get_db
            from database.models import AggregationRelationship
            
            # Invalidate this container
            self.invalidate_dpp(container_id)
            
            # Find all parent containers recursively
            with get_db() as db:
                # Find parents where this container is a child
                parents = db.query(AggregationRelationship.parent_sscc).filter(
                    AggregationRelationship.child_identifier == container_id,
                    AggregationRelationship.is_active == True
                ).distinct().all()
                
                # Recursively invalidate parents
                for parent in parents:
                    self.invalidate_container_hierarchy(parent[0])
        
        except Exception as e:
            print(f"Hierarchy invalidation error: {e}")
    
    def invalidate_pattern(self, pattern: str):
        """
        Invalidate all keys matching a pattern.
        
        Args:
            pattern: Redis key pattern (e.g., "dpp:*")
        """
        try:
            keys = self.redis_client.keys(pattern)
            if keys:
                self.redis_client.delete(*keys)
                print(f"Invalidated {len(keys)} cached DPPs")
        except Exception as e:
            print(f"Pattern invalidation error: {e}")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Dict with cache stats (size, hit rate estimates, etc.)
        """
        try:
            info = self.redis_client.info('stats')
            keys_count = self.redis_client.dbsize()
            
            return {
                "total_keys": keys_count,
                "dpp_keys": len(self.redis_client.keys(f"dpp:{self.version}:*")),
                "memory_used_mb": round(int(info.get('used_memory', 0)) / 1024 / 1024, 2),
                "total_connections": info.get('total_connections_received', 0),
                "total_commands": info.get('total_commands_processed', 0),
                "keyspace_hits": info.get('keyspace_hits', 0),
                "keyspace_misses": info.get('keyspace_misses', 0),
                "hit_rate": round(
                    info.get('keyspace_hits', 0) / 
                    max(info.get('keyspace_hits', 0) + info.get('keyspace_misses', 0), 1) * 100,
                    2
                )
            }
        except Exception as e:
            print(f"Stats error: {e}")
            return {}
    
    def health_check(self) -> bool:
        """
        Check if Redis is healthy.
        
        Returns:
            True if Redis is responsive, False otherwise
        """
        try:
            self.redis_client.ping()
            return True
        except:
            return False


# Global cache instance
_cache_instance = None

def get_cache() -> DPPCache:
    """Get or create global cache instance."""
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = DPPCache()
    return _cache_instance
