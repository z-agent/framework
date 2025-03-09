"""
Research Service
Integrates research agents with the trading system
"""

import logging
import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime
import json
from fastapi import BackgroundTasks
from pydantic import BaseModel

from src.agents.research_agents import ResearchSummaryAgent, CoinResearchAgent
from src.core.market_data import MarketDataService
from src.core.risk_analyzer import RiskAnalyzer

logger = logging.getLogger(__name__)

class ResearchRequest(BaseModel):
    """Model for research requests"""
    user_id: str
    token_symbol: Optional[str] = None
    topics: Optional[List[str]] = None
    lookback_days: int = 7
    min_engagement: int = 100

class ResearchService:
    """Service for managing research operations"""
    
    def __init__(self):
        self.summary_agent = ResearchSummaryAgent()
        self.coin_agent = CoinResearchAgent()
        self.market_data = MarketDataService()
        self.risk_analyzer = RiskAnalyzer()
        
        # Cache for research results
        self._research_cache = {}
        self._cache_ttl = 3600  # 1 hour
        
    async def get_social_summary(self, request: ResearchRequest) -> Dict[str, Any]:
        """Get summary of social media content"""
        try:
            cache_key = f"social_{request.user_id}_{request.topics}_{request.lookback_days}"
            
            # Check cache
            cached = self._get_cached_research(cache_key)
            print(f"Cached: {cached}")
            if cached:
                return cached
            
            # Collect content
            content = await self.summary_agent.collect_social_content(
                request.user_id,
                request.lookback_days
            )
            
            # Scan top tweets if topics provided
            if request.topics:
                top_tweets = await self.summary_agent.scan_top_tweets(
                    request.topics,
                    request.min_engagement
                )
                content.extend(top_tweets)
            
            # Generate summary
            summary = await self.summary_agent.generate_summary(content)
            
            # Cache results
            self._cache_research(cache_key, summary.dict())
            
            return summary.dict()
            
        except Exception as e:
            logger.error(f"Error getting social summary: {str(e)}")
            return {
                "error": str(e),
                "timestamp": datetime.now()
            }
    
    async def research_coin(self, request: ResearchRequest) -> Dict[str, Any]:
        """Research a specific coin"""
        try:
            if not request.token_symbol:
                raise ValueError("Token symbol is required")
                
            cache_key = f"coin_{request.token_symbol}"
            
            # Check cache
            cached = self._get_cached_research(cache_key)
            if cached:
                return cached
            
            # Perform research
            research = await self.coin_agent.research_coin(request.token_symbol)
            print(f"Research: {research}")
            
            # Enhance with market data
            market_data = await self.market_data.get_token_data(request.token_symbol)
            if market_data:
                research.market_metrics = market_data
            
            # Add risk assessment
            risk_assessment = await self.risk_analyzer.analyze_trade_risk(
                token=request.token_symbol,
                amount=0,  # Not trading, just analysis
                price=market_data.get("price", 0),
                market_data=market_data
            )
            research.risk_assessment = risk_assessment.dict()
            
            # Cache results
            self._cache_research(cache_key, research.dict())
            
            return research.dict()
            
        except Exception as e:
            logger.error(f"Error researching coin: {str(e)}")
            return {
                "error": str(e),
                "timestamp": datetime.now()
            }
    
    async def schedule_research(
        self,
        request: ResearchRequest,
        background_tasks: BackgroundTasks
    ) -> Dict[str, Any]:
        """Schedule research tasks"""
        try:
            tasks = []
            
            # Schedule social summary if topics provided
            if request.topics:
                tasks.append(self.get_social_summary(request))
            
            # Schedule coin research if token provided
            if request.token_symbol:
                tasks.append(self.research_coin(request))
            
            # Add tasks to background queue
            for task in tasks:
                background_tasks.add_task(task)
            
            return {
                "message": "Research tasks scheduled",
                "tasks": len(tasks),
                "timestamp": datetime.now()
            }
            
        except Exception as e:
            logger.error(f"Error scheduling research: {str(e)}")
            return {
                "error": str(e),
                "timestamp": datetime.now()
            }
    
    def _get_cached_research(self, key: str) -> Optional[Dict[str, Any]]:
        """Get cached research results"""
        if key in self._research_cache:
            data, timestamp = self._research_cache[key]
            if (datetime.now() - timestamp).seconds < self._cache_ttl:
                return data
        return None
    
    def _cache_research(self, key: str, data: Dict[str, Any]):
        """Cache research results"""
        self._research_cache[key] = (data, datetime.now())
        
    async def clear_cache(self):
        """Clear research cache"""
        self._research_cache.clear()
        logger.info("Research cache cleared") 