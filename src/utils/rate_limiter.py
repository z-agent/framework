"""
Rate Limiter Utility
Implements token bucket algorithm for API rate limiting
"""

import time
import asyncio
from typing import Dict, Any
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

@dataclass
class TokenBucket:
    """Token bucket for rate limiting"""
    rate: float  # tokens per second
    capacity: float  # bucket size
    tokens: float  # current tokens
    last_update: float  # last update timestamp

class RateLimiter:
    """Rate limiter using token bucket algorithm"""
    
    def __init__(self):
        self.buckets: Dict[str, TokenBucket] = {
            "twitter": TokenBucket(rate=300/900, capacity=300, tokens=300, last_update=time.time()),
            "telegram": TokenBucket(rate=20/60, capacity=20, tokens=20, last_update=time.time()),
            "discord": TokenBucket(rate=50/60, capacity=50, tokens=50, last_update=time.time())
        }
        
    async def acquire(self, key: str, tokens: int = 1) -> bool:
        """Acquire tokens from bucket"""
        if key not in self.buckets:
            return True
            
        bucket = self.buckets[key]
        now = time.time()
        
        # Add new tokens based on time passed
        time_passed = now - bucket.last_update
        new_tokens = time_passed * bucket.rate
        bucket.tokens = min(bucket.capacity, bucket.tokens + new_tokens)
        bucket.last_update = now
        
        # Check if we have enough tokens
        if bucket.tokens < tokens:
            wait_time = (tokens - bucket.tokens) / bucket.rate
            logger.warning(f"Rate limit hit for {key}, waiting {wait_time:.2f}s")
            await asyncio.sleep(wait_time)
            bucket.tokens = bucket.capacity
            
        bucket.tokens -= tokens
        return True
        
    async def wait_if_needed(self, key: str, tokens: int = 1):
        """Wait if rate limit would be exceeded"""
        await self.acquire(key, tokens)

# Global rate limiter instance
rate_limiter = RateLimiter() 