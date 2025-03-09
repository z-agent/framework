"""
Social Data Agent
Implements real-time social media data collection and analysis
"""

import logging
import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel
import httpx
from telethon import TelegramClient
import tweepy
import os

logger = logging.getLogger(__name__)

class SocialMetrics(BaseModel):
    """Model for social metrics"""
    mentions: int
    sentiment: float
    engagement: float
    top_influencers: List[Dict[str, Any]]
    trending_topics: List[Dict[str, Any]]
    timestamp: datetime

class SocialDataAgent:
    """Agent for collecting social media data"""
    
    def __init__(self):
        """Initialize social data agent"""
        # Twitter setup
        self.twitter_client = tweepy.Client(
            bearer_token=os.getenv("TWITTER_BEARER_TOKEN"),
            consumer_key=os.getenv("TWITTER_API_KEY"),
            consumer_secret=os.getenv("TWITTER_API_SECRET"),
            access_token=os.getenv("TWITTER_ACCESS_TOKEN"),
            access_token_secret=os.getenv("TWITTER_ACCESS_SECRET")
        )
        
        # Telegram setup
        self.telegram_client = TelegramClient(
            'research_bot',
            os.getenv("TELEGRAM_API_ID"),
            os.getenv("TELEGRAM_API_HASH")
        )
        
        # Cache settings
        self._cache = {}
        self._cache_ttl = 300  # 5 minutes for social data
        
    async def start(self):
        """Start Telegram client"""
        await self.telegram_client.start()
        
    async def close(self):
        """Close Telegram client"""
        await self.telegram_client.disconnect()
        
    async def get_twitter_metrics(
        self,
        query: str,
        days_back: int = 7
    ) -> Dict[str, Any]:
        """Get Twitter metrics for a topic"""
        try:
            # Check cache
            cache_key = f"twitter_{query}_{days_back}"
            cached = self._get_cached(cache_key)
            if cached:
                return cached
                
            # Search tweets
            tweets = self.twitter_client.search_recent_tweets(
                query=query,
                max_results=100,
                tweet_fields=['created_at', 'public_metrics']
            )
            
            # Process metrics
            metrics = {
                "mentions": 0,
                "total_likes": 0,
                "total_retweets": 0,
                "engagement_rate": 0,
                "top_tweets": []
            }
            
            if tweets.data:
                for tweet in tweets.data:
                    metrics["mentions"] += 1
                    metrics["total_likes"] += tweet.public_metrics["like_count"]
                    metrics["total_retweets"] += tweet.public_metrics["retweet_count"]
                    
                    # Store top tweets
                    engagement = tweet.public_metrics["like_count"] + tweet.public_metrics["retweet_count"]
                    if engagement > 100:  # Minimum engagement threshold
                        metrics["top_tweets"].append({
                            "text": tweet.text,
                            "engagement": engagement,
                            "created_at": tweet.created_at
                        })
                
                # Calculate engagement rate
                metrics["engagement_rate"] = (
                    metrics["total_likes"] + metrics["total_retweets"]
                ) / metrics["mentions"] if metrics["mentions"] > 0 else 0
                
            # Cache results
            self._cache_data(cache_key, metrics)
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error getting Twitter metrics: {str(e)}")
            raise
            
    async def get_telegram_metrics(
        self,
        channels: List[str],
        query: str,
        days_back: int = 7
    ) -> Dict[str, Any]:
        """Get Telegram metrics from specified channels"""
        try:
            # Check cache
            cache_key = f"telegram_{query}_{days_back}"
            cached = self._get_cached(cache_key)
            if cached:
                return cached
                
            metrics = {
                "mentions": 0,
                "total_views": 0,
                "total_forwards": 0,
                "channels_activity": {},
                "top_messages": []
            }
            
            # Get messages from each channel
            for channel in channels:
                try:
                    messages = await self.telegram_client.get_messages(
                        channel,
                        search=query,
                        limit=100
                    )
                    
                    channel_metrics = {
                        "mentions": 0,
                        "views": 0,
                        "forwards": 0
                    }
                    
                    for msg in messages:
                        if msg.date > datetime.now() - timedelta(days=days_back):
                            metrics["mentions"] += 1
                            channel_metrics["mentions"] += 1
                            
                            if hasattr(msg, 'views'):
                                metrics["total_views"] += msg.views
                                channel_metrics["views"] += msg.views
                                
                            if hasattr(msg, 'forwards'):
                                metrics["total_forwards"] += msg.forwards
                                channel_metrics["forwards"] += msg.forwards
                                
                            # Store top messages
                            if msg.views > 1000:  # Minimum views threshold
                                metrics["top_messages"].append({
                                    "text": msg.text,
                                    "views": msg.views,
                                    "channel": channel,
                                    "date": msg.date
                                })
                                
                    metrics["channels_activity"][channel] = channel_metrics
                    
                except Exception as e:
                    logger.error(f"Error processing channel {channel}: {str(e)}")
                    continue
                    
            # Cache results
            self._cache_data(cache_key, metrics)
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error getting Telegram metrics: {str(e)}")
            raise
            
    async def analyze_social_sentiment(
        self,
        twitter_data: Dict[str, Any],
        telegram_data: Dict[str, Any]
    ) -> SocialMetrics:
        """Analyze combined social metrics"""
        try:
            total_mentions = (
                twitter_data.get("mentions", 0) +
                telegram_data.get("mentions", 0)
            )
            
            # Combine top content
            top_content = []
            
            # Add Twitter content
            for tweet in twitter_data.get("top_tweets", []):
                top_content.append({
                    "platform": "twitter",
                    "content": tweet["text"],
                    "engagement": tweet["engagement"],
                    "timestamp": tweet["created_at"]
                })
                
            # Add Telegram content
            for msg in telegram_data.get("top_messages", []):
                top_content.append({
                    "platform": "telegram",
                    "content": msg["text"],
                    "engagement": msg["views"],
                    "timestamp": msg["date"]
                })
                
            # Sort by engagement
            top_content.sort(key=lambda x: x["engagement"], reverse=True)
            
            return SocialMetrics(
                mentions=total_mentions,
                sentiment=0.0,  # TODO: Implement sentiment analysis
                engagement=(
                    twitter_data.get("engagement_rate", 0) +
                    telegram_data.get("total_views", 0) / max(telegram_data.get("mentions", 1), 1)
                ) / 2,
                top_influencers=[],  # TODO: Implement influencer analysis
                trending_topics=[],  # TODO: Implement topic extraction
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Error analyzing social sentiment: {str(e)}")
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