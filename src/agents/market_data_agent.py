"""
Market Data Agent
Implements real-time market data collection and analysis
"""

import logging
import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel
import httpx
import os

logger = logging.getLogger(__name__)

class MarketMetrics(BaseModel):
    """Model for market metrics"""
    price: float
    volume_24h: float
    market_cap: float
    price_change_24h: float
    liquidity: float
    timestamp: datetime

class MarketDataAgent:
    """Agent for collecting real market data"""
    
    def __init__(self):
        """Initialize market data agent"""
        self.birdeye_api_key = os.getenv("BIRDEYE_API_KEY")
        self.client = httpx.AsyncClient(timeout=30.0)
        
        # Cache settings
        self._cache = {}
        self._cache_ttl = 60  # 1 minute for price data
        
    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()
        
    async def get_token_metrics(self, token_address: str) -> MarketMetrics:
        """Get real-time token metrics from Birdeye"""
        try:
            # Check cache
            cache_key = f"metrics_{token_address}"
            cached = self._get_cached(cache_key)
            if cached:
                return cached
                
            # Get data from Birdeye
            response = await self.client.get(
                f"https://public-api.birdeye.so/public/token_data",
                params={"token_address": token_address},
                headers={"X-API-KEY": self.birdeye_api_key}
            )
            response.raise_for_status()
            data = response.json()
            
            # Parse metrics
            metrics = MarketMetrics(
                price=float(data["price"]),
                volume_24h=float(data["volume24h"]),
                market_cap=float(data["marketCap"]),
                price_change_24h=float(data["priceChange24h"]),
                liquidity=float(data["liquidity"]),
                timestamp=datetime.now()
            )
            
            # Cache results
            self._cache_data(cache_key, metrics)
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error getting token metrics: {str(e)}")
            raise
            
    async def get_price_history(
        self,
        token_address: str,
        days: int = 7
    ) -> List[Dict[str, float]]:
        """Get historical price data"""
        try:
            # Get data from Birdeye
            response = await self.client.get(
                f"https://public-api.birdeye.so/public/history",
                params={
                    "token_address": token_address,
                    "type": "1D",
                    "limit": days
                },
                headers={"X-API-KEY": self.birdeye_api_key}
            )
            response.raise_for_status()
            data = response.json()
            
            return [
                {
                    "timestamp": item["timestamp"],
                    "price": float(item["value"]),
                    "volume": float(item["volume"])
                }
                for item in data["data"]
            ]
            
        except Exception as e:
            logger.error(f"Error getting price history: {str(e)}")
            raise
            
    async def get_dex_metrics(
        self,
        token_address: str
    ) -> Dict[str, Any]:
        """Get DEX trading metrics"""
        try:
            response = await self.client.get(
                f"https://public-api.birdeye.so/public/dex_data",
                params={"token_address": token_address},
                headers={"X-API-KEY": self.birdeye_api_key}
            )
            response.raise_for_status()
            
            return response.json()
            
        except Exception as e:
            logger.error(f"Error getting DEX metrics: {str(e)}")
            raise
            
    def _get_cached(self, key: str) -> Optional[Any]:
        """Get data from cache if not expired"""
        if key in self._cache:
            data, timestamp = self._cache[key]
            if (datetime.now() - timestamp).seconds < self._cache_ttl:
                return data
        return None
        
    def _cache_data(self, key: str, data: Any):
        """Cache data with timestamp"""
        self._cache[key] = (data, datetime.now()) 