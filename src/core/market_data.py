"""
Market Data Service for DeFi Operations
Provides real-time market data and analysis with DEX integration and social sentiment
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import numpy as np
import logging
import aiohttp
import asyncio
from cachetools import TTLCache
from supabase import create_client, Client
import os
from decimal import Decimal
import json
from dotenv import load_dotenv
import requests

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

class PerplexityClient:
    def __init__(self):
        self.api_key = os.getenv("PERPLEXITY_API_KEY")
        self.api_url = "https://api.perplexity.ai/chat/completions"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    async def analyze(self, query: str) -> Dict[str, Any]:
        data = {
            "model": "sonar",
            "messages": [
                {
                    "role": "system",
                    "content": "You are a helpful assistant that provides interesting, accurate, and concise facts. Respond with only one fascinating fact, kept under 100 words."
                },
                {
                    "role": "user",
                    "content": query
                }
            ],
            "max_tokens": 150,
            "temperature": 0.7
        }
        
        try:
            response = requests.post(self.api_url, headers=self.headers, json=data)
            response.raise_for_status()  # Raise an exception for 4XX/5XX responses
            result = response.json()
            return result["choices"][0]["message"]["content"]
        except requests.exceptions.RequestException as e:
            return f"Error making API request: {str(e)}"
        except (KeyError, IndexError) as e:
            return f"Error parsing API response: {str(e)}"
        except Exception as e:
            return f"Unexpected error: {str(e)}"

        pass

class MarketDataService:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.price_cache = TTLCache(maxsize=1000, ttl=60)  # 1 minute cache
        self.liquidity_cache = TTLCache(maxsize=1000, ttl=300)  # 5 minute cache
        self.volume_cache = TTLCache(maxsize=1000, ttl=300)  # 5 minute cache
        
        # Initialize Supabase client
        self.supabase_url = os.getenv("SUPABASE_URL")
        self.supabase_key = os.getenv("SUPABASE_KEY")
        if not self.supabase_url or not self.supabase_key:
            self.logger.error("Missing Supabase credentials!")
            self.logger.debug(f"Available environment variables: {list(os.environ.keys())}")
        self.supabase: Client = create_client(self.supabase_url, self.supabase_key)
        self.logger.info(f"Initialized Supabase client with URL: {self.supabase_url}")
        
        # Jupiter API endpoint
        self.jupiter_api = "https://price.jup.ag/v4"
        
        # Birdeye API
        self.birdeye_api = "https://public-api.birdeye.so/v1"
        self.birdeye_key = os.getenv("BIRDEYE_API_KEY")
        if not self.birdeye_key:
            self.logger.error("Missing Birdeye API key!")
        
        self.logger.info("MarketDataService initialized")

    async def get_token_data(self, token_symbol: str) -> Dict[str, Any]:
        """Get comprehensive token data including mindshare metrics"""
        try:
            # Get mindshare data
            mindshare_data = await self._fetch_mindshare_data(token_symbol)
            if not mindshare_data:
                return {}
                
            # Calculate pressures if not available
            volume = float(mindshare_data.get('volume', 0))
            price_change = float(mindshare_data.get('price_change_24h', 0))
            volume_ma = float(mindshare_data.get('volume_ma_24h', 0))
            
            # Calculate buy/sell pressure based on price action and volume
            if price_change > 0:
                buy_pressure = volume * abs(price_change)
                sell_pressure = volume_ma * 0.2  # Base sell pressure
            else:
                buy_pressure = volume_ma * 0.2  # Base buy pressure
                sell_pressure = volume * abs(price_change)
                
            mindshare_data['buy_pressure'] = buy_pressure
            mindshare_data['sell_pressure'] = sell_pressure
            
            # Log the processed data
            logger.info(f"Processed enhanced market data for {token_symbol}: price=${mindshare_data.get('price', 0)}, mindshare_score={mindshare_data.get('mindshare_score', 0)}")
            
            return mindshare_data
            
        except Exception as e:
            logger.error(f"Error getting token data: {str(e)}", exc_info=True)
            return {}

    def _determine_trend(self, data: Dict[str, Any]) -> str:
        """Determine trend based on multiple indicators"""
        try:
            # Get moving averages
            price = float(data.get("price", 0))
            ma_6h = float(data.get("price_ma_6h", 0))
            ma_24h = float(data.get("price_ma_24h", 0))
            
            # Get momentum indicators
            price_momentum = float(data.get("price_momentum", 0))
            rsi = float(data.get("rsi", 50))
            
            # Determine trend
            if price > ma_6h > ma_24h and price_momentum > 0 and rsi > 60:
                return "strong_uptrend"
            elif price > ma_6h > ma_24h:
                return "uptrend"
            elif price < ma_6h < ma_24h and price_momentum < 0 and rsi < 40:
                return "strong_downtrend"
            elif price < ma_6h < ma_24h:
                return "downtrend"
            else:
                return "neutral"
                
        except Exception as e:
            self.logger.error(f"Error determining trend: {str(e)}")
            return "neutral"

    async def _fetch_mindshare_data(self, token_symbol: str) -> Dict[str, Any]:
        """Fetch mindshare data from Supabase"""
        try:
            # Execute query without await
            data = self.supabase.table('mindshare_analysis').select('*').eq('token_symbol', token_symbol).order('created_at', desc=True).limit(1).execute()
            
            if not data.data:
                return {}
            
            mindshare_data = data.data[0]
            logger.info(f"mindshare data: {len(data.data)}")
            
            # Calculate pressures from volume and price change
            volume = float(mindshare_data.get('volume', 0))
            price_change = float(mindshare_data.get('price_change_24h', 0))
            volume_ma = float(mindshare_data.get('volume_ma_24h', 0))
            
            # Calculate buy/sell pressure based on price action and volume
            if price_change > 0:
                buy_pressure = volume * abs(price_change)
                sell_pressure = volume_ma * 0.2  # Base sell pressure
            else:
                buy_pressure = volume_ma * 0.2  # Base buy pressure
                sell_pressure = volume * abs(price_change)
                
            # Calculate momentum metrics
            price_ma_6h = float(mindshare_data.get('price_ma_6h', 0))
            price_ma_24h = float(mindshare_data.get('price_ma_24h', 0))
            
            # Price momentum from MA crossover
            if price_ma_24h != 0:
                price_momentum = ((price_ma_6h - price_ma_24h) / price_ma_24h) * 100
            else:
                price_momentum = 0
                
            # Volume momentum from current vs MA
            if volume_ma != 0:
                volume_momentum = ((volume - volume_ma) / volume_ma) * 100
            else:
                volume_momentum = 0
                
            # Pressure momentum from buy/sell pressure ratio change
            total_pressure = buy_pressure + sell_pressure
            if total_pressure > 0:
                pressure_ratio = buy_pressure / total_pressure
                pressure_momentum = (pressure_ratio - 0.5) * 100  # Convert to percentage
            else:
                pressure_momentum = 0
                
            # Market impact from volume ratio
            market_impact = min(1.0, volume / (volume_ma + 1e-6))
            
            # Update mindshare data with calculated metrics
            mindshare_data.update({
                'buy_pressure': buy_pressure,
                'sell_pressure': sell_pressure,
                'pressure_momentum': pressure_momentum,
                'volume_momentum': volume_momentum,
                'price_momentum': price_momentum,
                'market_impact': market_impact
            })
            
            logger.info(f"\nMindshare data: {mindshare_data}\n")
            return mindshare_data
            
        except Exception as e:
            logger.error(f"Error fetching mindshare data: {str(e)}", exc_info=True)
            return {}

    def _calculate_momentum(self, values: List[float], periods: int = 6) -> float:
        """Calculate momentum using rate of change"""
        if not values or len(values) < 2:
            return 0.0
        
        try:
            # Calculate rate of change
            current = values[-1]
            previous = values[0] if len(values) >= periods else values[0]
            
            if previous == 0:
                return 0.0
            
            momentum = ((current - previous) / previous) * 100
            return momentum
            
        except Exception as e:
            logger.error(f"Error calculating momentum: {str(e)}", exc_info=True)
            return 0.0

    async def get_trending_tokens(self) -> List[Dict[str, Any]]:
        """Get list of trending tokens based on mindshare analysis"""
        try:
            self.logger.info("Fetching trending tokens from Supabase")
            
            # Get latest record for each token using direct query
            response = self.supabase.table("mindshare_analysis") \
                .select("*") \
                .execute()
            
            if response.data:
                # Group by token and get latest record for each
                token_data = {}
                for record in response.data:
                    token = record.get('token_symbol')
                    timestamp = record.get('timestamp')
                    if token not in token_data or timestamp > token_data[token].get('timestamp'):
                        token_data[token] = record
                
                # Convert to list and sort by our scoring criteria
                latest_records = list(token_data.values())
                self.logger.info(f"Found {len(latest_records)} unique tokens")
                
                # Sort by combined score (mindshare, engagement, sentiment)
                sorted_tokens = sorted(
                    latest_records,
                    key=lambda x: (
                        float(x.get('mindshare_index', 0)) * 0.4 +
                        float(x.get('engagement', 0)) * 0.3 +
                        float(x.get('sentiment', 0)) * 0.3
                    ),
                    reverse=True
                )
                
                # Return top 10 tokens
                top_tokens = sorted_tokens[:10]
                self.logger.info(f"Returning top {len(top_tokens)} trending tokens")
                return top_tokens
                
            self.logger.warning("No trending tokens found")
            return []
            
        except Exception as e:
            self.logger.error(f"Error fetching trending tokens: {str(e)}", exc_info=True)
            return []

    async def _fetch_price_data(self, token_address: str) -> Dict[str, Any]:
        """Fetch price data from Jupiter and Birdeye"""
        if token_address in self.price_cache:
            return self.price_cache[token_address]
            
        try:
            async with aiohttp.ClientSession() as session:
                # Get Jupiter price
                jupiter_url = f"{self.jupiter_api}/price?ids={token_address}"
                async with session.get(jupiter_url) as resp:
                    jupiter_data = await resp.json()
                
                # Get Birdeye price history
                birdeye_url = f"{self.birdeye_api}/token/price?address={token_address}"
                headers = {"X-API-KEY": self.birdeye_key}
                async with session.get(birdeye_url, headers=headers) as resp:
                    birdeye_data = await resp.json()
                
                price_data = {
                    "current_price": Decimal(str(jupiter_data.get("data", {}).get(token_address, {}).get("price", 0))),
                    "price_history": birdeye_data.get("data", {}).get("price_history", []),
                    "price_change_24h": birdeye_data.get("data", {}).get("price_change_24h", 0),
                }
                
                self.price_cache[token_address] = price_data
                return price_data
                
        except Exception as e:
            logger.error(f"Error fetching price data: {str(e)}", exc_info=True)
            return {}
            
    async def _fetch_liquidity_data(self, token_address: str) -> Dict[str, Any]:
        """Fetch liquidity data from Birdeye"""
        if token_address in self.liquidity_cache:
            return self.liquidity_cache[token_address]
            
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.birdeye_api}/token/liquidity?address={token_address}"
                headers = {"X-API-KEY": self.birdeye_key}
                
                async with session.get(url, headers=headers) as resp:
                    data = await resp.json()
                    
                liquidity_data = {
                    "liquidity": data.get("data", {}).get("liquidity", 0),
                    "liquidity_change_24h": data.get("data", {}).get("liquidity_change_24h", 0),
                }
                
                self.liquidity_cache[token_address] = liquidity_data
                return liquidity_data
                
        except Exception as e:
            logger.error(f"Error fetching liquidity data: {str(e)}", exc_info=True)
            return {}
            
    async def _fetch_volume_data(self, token_address: str) -> Dict[str, Any]:
        """Fetch volume-related data"""
        if token_address in self.volume_cache:
            return self.volume_cache[token_address]
            
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"https://api.example.com/volume/{token_address}") as resp:
                    volume_data = await resp.json()
                    
            data = {
                "volume_24h": volume_data.get("volume_24h", 0),
                "volume_change_24h": volume_data.get("change_24h", 0),
                "volume_ratio": volume_data.get("volume_ratio", 1)  # Compared to average
            }
            
            self.volume_cache[token_address] = data
            return data
            
        except Exception as e:
            logger.error(f"Error fetching volume data: {str(e)}", exc_info=True)
            return {}
            
    def _calculate_volatility(self, price_history: List[float]) -> float:
        """Calculate historical volatility"""
        if len(price_history) < 2:
            return 0
            
        returns = np.diff(np.log(price_history))
        return float(np.std(returns) * np.sqrt(365))
        
    def _analyze_trend(self, price_history: List[float]) -> str:
        """Analyze price trend"""
        if len(price_history) < 2:
            return "neutral"
            
        # Calculate moving averages
        short_ma = np.mean(price_history[-7:])
        long_ma = np.mean(price_history[-30:])
        
        # Calculate momentum
        momentum = (price_history[-1] / price_history[-7]) - 1
        
        if short_ma > long_ma and momentum > 0.1:
            return "strong_uptrend"
        elif short_ma > long_ma:
            return "uptrend"
        elif short_ma < long_ma and momentum < -0.1:
            return "strong_downtrend"
        elif short_ma < long_ma:
            return "downtrend"
        else:
            return "neutral"
            
    async def _calculate_market_correlation(
        self,
        token_address: str,
        price_history: List[float]
    ) -> float:
        """Calculate correlation with market"""
        try:
            # Fetch market (SOL) price history
            async with aiohttp.ClientSession() as session:
                async with session.get("https://api.example.com/price_history/SOL") as resp:
                    market_data = await resp.json()
                    
            market_prices = market_data.get("prices", [])
            
            if len(price_history) < 2 or len(market_prices) < 2:
                return 0
                
            # Calculate correlation
            token_returns = np.diff(np.log(price_history))
            market_returns = np.diff(np.log(market_prices))
            
            # Ensure same length
            min_length = min(len(token_returns), len(market_returns))
            correlation = np.corrcoef(
                token_returns[:min_length],
                market_returns[:min_length]
            )[0, 1]
            
            return float(correlation)
            
        except Exception as e:
            logger.error(f"Error calculating market correlation: {str(e)}", exc_info=True)
            return 0 