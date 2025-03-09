"""
Cache Manager
Implements local memory caching with TTL
"""

import json
import time
from typing import Dict, Any, Optional, Union
from datetime import datetime
import logging
from functools import wraps
import os

logger = logging.getLogger(__name__)

class CacheManager:
    """Local memory cache manager"""
    
    def __init__(self):
        # Local cache
        self._local_cache: Dict[str, tuple[Any, float]] = {}
        
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        try:
            # Check local cache
            if key in self._local_cache:
                value, expiry = self._local_cache[key]
                if time.time() < expiry:
                    return value
                else:
                    del self._local_cache[key]
                    
            return None
            
        except Exception as e:
            logger.error(f"Cache get error: {str(e)}")
            return None
            
    async def set(
        self,
        key: str,
        value: Any,
        ttl: int = 3600,
        background: bool = False
    ) -> bool:
        """Set value in cache"""
        try:
            # Store in local cache
            self._local_cache[key] = (value, time.time() + ttl)
            return True
            
        except Exception as e:
            logger.error(f"Cache set error: {str(e)}")
            return False
            
    async def delete(self, key: str) -> bool:
        """Delete value from cache"""
        try:
            # Delete from local cache
            if key in self._local_cache:
                del self._local_cache[key]
                
            return True
            
        except Exception as e:
            logger.error(f"Cache delete error: {str(e)}")
            return False
            
    async def clear(self) -> bool:
        """Clear all cache"""
        try:
            # Clear local cache
            self._local_cache.clear()
            return True
            
        except Exception as e:
            logger.error(f"Cache clear error: {str(e)}")
            return False
            
    def cached(self, ttl: int = 3600):
        """Decorator for caching function results"""
        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                # Generate cache key
                key = f"{func.__name__}:{args}:{kwargs}"
                
                # Try getting from cache
                cached_value = await self.get(key)
                if cached_value is not None:
                    return cached_value
                    
                # Execute function
                result = await func(*args, **kwargs)
                
                # Store in cache
                await self.set(key, result, ttl=ttl)
                
                return result
            return wrapper
        return decorator
        
# Global cache manager instance
cache_manager = CacheManager() 