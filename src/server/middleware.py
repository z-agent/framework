#!/usr/bin/env python3
"""
🔥 PERFORMANCE MIDDLEWARE
Rate limiting, caching, and monitoring for production scaling
"""

import time
import redis
import json
from typing import Dict, Any
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
import asyncio
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)

class RateLimiter:
    """Rate limiting middleware"""
    
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis_client = redis.from_url(redis_url)
        self.limits = {
            "tool_search": {"per_minute": 60, "per_hour": 1000},
            "agent_call": {"per_minute": 30, "per_hour": 500},
            "multimodal_agent_call": {"per_minute": 10, "per_hour": 100}
        }
    
    async def check_rate_limit(self, request: Request, endpoint: str) -> bool:
        """Check if request is within rate limits"""
        client_ip = request.client.host
        current_time = int(time.time())
        
        # Check per-minute limit
        minute_key = f"rate_limit:{endpoint}:{client_ip}:{current_time // 60}"
        minute_count = self.redis_client.get(minute_key)
        
        if minute_count and int(minute_count) >= self.limits.get(endpoint, {}).get("per_minute", 60):
            return False
        
        # Check per-hour limit
        hour_key = f"rate_limit:{endpoint}:{client_ip}:{current_time // 3600}"
        hour_count = self.redis_client.get(hour_key)
        
        if hour_count and int(hour_count) >= self.limits.get(endpoint, {}).get("per_hour", 1000):
            return False
        
        # Increment counters
        self.redis_client.incr(minute_key, ex=60)
        self.redis_client.incr(hour_key, ex=3600)
        
        return True

class CacheManager:
    """Caching middleware for tool results"""
    
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis_client = redis.from_url(redis_url)
        self.default_ttl = 300  # 5 minutes
    
    async def get_cached_result(self, cache_key: str) -> Dict[str, Any]:
        """Get cached result if available"""
        try:
            cached = self.redis_client.get(cache_key)
            if cached:
                return json.loads(cached)
        except Exception as e:
            logger.warning(f"Cache retrieval failed: {e}")
        return None
    
    async def cache_result(self, cache_key: str, result: Dict[str, Any], ttl: int = None):
        """Cache result with TTL"""
        try:
            ttl = ttl or self.default_ttl
            self.redis_client.setex(cache_key, ttl, json.dumps(result))
        except Exception as e:
            logger.warning(f"Cache storage failed: {e}")
    
    def generate_cache_key(self, endpoint: str, params: Dict[str, Any]) -> str:
        """Generate cache key from endpoint and parameters"""
        param_str = json.dumps(params, sort_keys=True)
        return f"cache:{endpoint}:{hash(param_str)}"

class PerformanceMonitor:
    """Performance monitoring middleware"""
    
    def __init__(self):
        self.metrics = defaultdict(list)
        self.request_times = defaultdict(list)
    
    async def record_request(self, endpoint: str, duration: float, status_code: int):
        """Record request metrics"""
        self.metrics[endpoint].append({
            "timestamp": time.time(),
            "duration": duration,
            "status_code": status_code
        })
        
        # Keep only last 1000 requests per endpoint
        if len(self.metrics[endpoint]) > 1000:
            self.metrics[endpoint] = self.metrics[endpoint][-1000:]
    
    def get_metrics(self, endpoint: str = None) -> Dict[str, Any]:
        """Get performance metrics"""
        if endpoint:
            return self._calculate_endpoint_metrics(endpoint)
        
        return {
            "overall": self._calculate_overall_metrics(),
            "endpoints": {ep: self._calculate_endpoint_metrics(ep) for ep in self.metrics.keys()}
        }
    
    def _calculate_endpoint_metrics(self, endpoint: str) -> Dict[str, Any]:
        """Calculate metrics for specific endpoint"""
        requests = self.metrics[endpoint]
        if not requests:
            return {}
        
        durations = [r["duration"] for r in requests]
        status_codes = [r["status_code"] for r in requests]
        
        return {
            "total_requests": len(requests),
            "avg_duration": sum(durations) / len(durations),
            "max_duration": max(durations),
            "min_duration": min(durations),
            "success_rate": len([s for s in status_codes if s < 400]) / len(status_codes),
            "error_rate": len([s for s in status_codes if s >= 400]) / len(status_codes)
        }
    
    def _calculate_overall_metrics(self) -> Dict[str, Any]:
        """Calculate overall metrics"""
        all_requests = []
        for requests in self.metrics.values():
            all_requests.extend(requests)
        
        if not all_requests:
            return {}
        
        durations = [r["duration"] for r in all_requests]
        status_codes = [r["status_code"] for r in all_requests]
        
        return {
            "total_requests": len(all_requests),
            "avg_duration": sum(durations) / len(durations),
            "max_duration": max(durations),
            "min_duration": min(durations),
            "success_rate": len([s for s in status_codes if s < 400]) / len(status_codes),
            "error_rate": len([s for s in status_codes if s >= 400]) / len(status_codes)
        }

# Global instances
rate_limiter = RateLimiter()
cache_manager = CacheManager()
performance_monitor = PerformanceMonitor()

async def performance_middleware(request: Request, call_next):
    """Main performance middleware"""
    start_time = time.time()
    
    # Extract endpoint name
    endpoint = request.url.path.replace("/", "_").strip("_")
    
    # Check rate limits
    if not await rate_limiter.check_rate_limit(request, endpoint):
        return JSONResponse(
            status_code=429,
            content={"error": "Rate limit exceeded", "endpoint": endpoint}
        )
    
    # Check cache for GET requests
    if request.method == "GET":
        params = dict(request.query_params)
        cache_key = cache_manager.generate_cache_key(endpoint, params)
        cached_result = await cache_manager.get_cached_result(cache_key)
        
        if cached_result:
            return JSONResponse(content=cached_result)
    
    # Process request
    try:
        response = await call_next(request)
        duration = time.time() - start_time
        
        # Record metrics
        await performance_monitor.record_request(endpoint, duration, response.status_code)
        
        # Cache successful GET responses
        if request.method == "GET" and response.status_code == 200:
            try:
                response_body = response.body.decode()
                result = json.loads(response_body)
                await cache_manager.cache_result(cache_key, result)
            except:
                pass  # Skip caching if response parsing fails
        
        return response
        
    except Exception as e:
        duration = time.time() - start_time
        await performance_monitor.record_request(endpoint, duration, 500)
        raise 