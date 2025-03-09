"""
Production-grade NLP Service for DeFi interactions
Implements advanced NLP capabilities with proper error handling, monitoring, and caching
"""

from typing import Dict, Any, Optional, List, Tuple
from .nlp import NLPEngine, Intent, IntentType, TradeParams
from pydantic import BaseModel, Field
import logging
from fastapi import HTTPException
from redis import Redis
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode
import json
from datetime import datetime, timedelta
import hashlib
from tenacity import retry, stop_after_attempt, wait_exponential
import asyncio
from concurrent.futures import ThreadPoolExecutor

# Configure logging
logger = logging.getLogger(__name__)

# Configure tracing
tracer = trace.get_tracer(__name__)

class NLPRequest(BaseModel):
    """Request model for NLP processing"""
    text: str
    user_id: Optional[str] = Field(None, description="User ID for context tracking")
    context: Optional[Dict[str, Any]] = Field(None, description="Additional context")
    chain_id: str = Field("mainnet-beta", description="Blockchain network")
    risk_level: str = Field("medium", description="User risk preference")
    max_slippage: float = Field(1.0, description="Maximum allowed slippage")

class NLPResponse(BaseModel):
    """Response model for NLP processing"""
    intent: Intent
    explanation: str
    action_params: Optional[Dict[str, Any]] = None
    suggestions: Optional[Dict[str, Any]] = None
    risk_assessment: Optional[Dict[str, Any]] = None
    request_id: str = Field(..., description="Unique request identifier")
    processing_time: float = Field(..., description="Processing time in seconds")

class NLPService:
    def __init__(self, cache_url: Optional[str] = None, model_path: Optional[str] = None):
        """Initialize NLP service with optional caching"""
        self.engine = NLPEngine()
        self.context_store = {}  # In-memory context store
        
        # Initialize cache if URL provided
        self.cache = Redis.from_url(cache_url) if cache_url else None
        
        # Initialize thread pool for CPU-intensive tasks
        self.executor = ThreadPoolExecutor(max_workers=4)
        
    async def process_request(self, request: NLPRequest) -> NLPResponse:
        """Process a natural language request with full observability and error handling"""
        start_time = datetime.now()
        request_id = self._generate_request_id(request)
        
        with tracer.start_as_current_span("nlp_process_request") as span:
            try:
                # Check cache first
                if self.cache:
                    cached_response = await self._get_cached_response(request_id)
                    if cached_response:
                        logger.info(f"Cache hit for request {request_id}")
                        return cached_response
                
                # Process the message
                with tracer.start_span("intent_classification") as intent_span:
                    intent = await self._classify_intent_with_context(request)
                    intent_span.set_attribute("intent_type", intent.type)
                
                # Get explanation with proper context
                with tracer.start_span("generate_explanation"):
                    explanation = await self._generate_contextual_explanation(intent, request)
                
                # Parse specific parameters based on intent
                action_params = None
                suggestions = None
                risk_assessment = None
                
                if intent.type == IntentType.TRADE:
                    action_params = await self._handle_trade_intent(request)
                    suggestions = await self._generate_trade_suggestions(action_params)
                    risk_assessment = await self._assess_trade_risk(action_params, request)
                elif intent.type == IntentType.ANALYZE:
                    action_params = await self._handle_analysis_intent(request)
                    suggestions = await self._generate_analysis_suggestions(action_params)
                elif intent.type == IntentType.MONITOR:
                    action_params = await self._handle_monitor_intent(request)
                elif intent.type == IntentType.STAKE:
                    action_params = await self._handle_stake_intent(request)
                    suggestions = await self._generate_stake_suggestions(action_params)
                    risk_assessment = await self._assess_stake_risk(action_params, request)
                
                processing_time = (datetime.now() - start_time).total_seconds()
                
                response = NLPResponse(
                    intent=intent,
                    explanation=explanation,
                    action_params=action_params,
                    suggestions=suggestions,
                    risk_assessment=risk_assessment,
                    request_id=request_id,
                    processing_time=processing_time
                )
                
                # Cache the response
                if self.cache:
                    await self._cache_response(request_id, response)
                
                # Log metrics
                self._log_metrics(request, response)
                
                return response
                
            except Exception as e:
                logger.error(f"Error processing NLP request: {str(e)}", exc_info=True)
                span.set_status(Status(StatusCode.ERROR))
                span.record_exception(e)
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to process request: {str(e)}"
                )
    
    async def _classify_intent_with_context(self, request: NLPRequest) -> Intent:
        """Classify intent considering user context and history"""
        with tracer.start_span("intent_classification_detailed"):
            # Get user context
            user_context = self.context_store.get(request.user_id, {})
            
            # Combine with request context
            full_context = {
                **user_context,
                **(request.context or {}),
                "chain_id": request.chain_id,
                "risk_level": request.risk_level
            }
            
            # Use thread pool for CPU-intensive classification
            intent = await asyncio.get_event_loop().run_in_executor(
                self.executor,
                self.engine.process_message,
                request.text
            )
            
            # Enhance intent with context
            intent.context = full_context
            return intent
    
    async def _generate_contextual_explanation(
        self, 
        intent: Intent, 
        request: NLPRequest
    ) -> str:
        """Generate explanation considering user context and preferences"""
        base_explanation = self.engine.get_explanation(intent)
        
        # Add context-specific details
        context_details = []
        if request.risk_level == "low":
            context_details.append("Following conservative risk parameters.")
        elif request.risk_level == "high":
            context_details.append("Operating with higher risk tolerance.")
            
        if request.chain_id != "mainnet-beta":
            context_details.append(f"Operating on {request.chain_id} network.")
            
        if context_details:
            base_explanation += f" {' '.join(context_details)}"
            
        return base_explanation
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def _handle_trade_intent(self, request: NLPRequest) -> Dict[str, Any]:
        """Handle trade intent with retries and validation"""
        trade_params = self.engine.parse_trade_params(request.text)
        if not trade_params:
            return {
                "error": "Could not parse trade parameters",
                "examples": [
                    "buy 100 SOL",
                    "sell 50 BONK when price is above 1.5",
                    "buy 1000 USDC worth of JTO"
                ]
            }
        
        # Validate and enhance trade parameters
        enhanced_params = await self._enhance_trade_params(trade_params, request)
        return enhanced_params
    
    async def _enhance_trade_params(
        self, 
        params: TradeParams, 
        request: NLPRequest
    ) -> Dict[str, Any]:
        """Enhance trade parameters with smart defaults and validations"""
        enhanced = params.dict()
        
        # Add smart slippage based on token and amount
        enhanced["smart_slippage"] = await self._calculate_smart_slippage(
            params.token,
            params.amount,
            request.max_slippage
        )
        
        # Add MEV protection if amount is significant
        if params.amount * await self._get_token_price(params.token) > 1000:
            enhanced["mev_protection"] = True
            
        # Add route optimization
        enhanced["route_optimization"] = await self._optimize_trade_route(
            params.token,
            params.amount
        )
        
        return enhanced
    
    async def _calculate_smart_slippage(
        self, 
        token: str, 
        amount: float, 
        max_slippage: float
    ) -> float:
        """Calculate optimal slippage based on token liquidity and amount"""
        # Implementation would include:
        # 1. Token liquidity analysis
        # 2. Historical volatility check
        # 3. Amount impact calculation
        return min(max_slippage, 0.5)  # Simplified for demo
    
    async def _get_token_price(self, token: str) -> float:
        """Get token price with caching"""
        cache_key = f"price:{token}"
        if self.cache:
            cached_price = self.cache.get(cache_key)
            if cached_price:
                return float(cached_price)
        
        # Implement actual price fetching
        return 1.0  # Simplified for demo
    
    async def _optimize_trade_route(self, token: str, amount: float) -> Dict[str, Any]:
        """Optimize trading route for best execution"""
        return {
            "path": ["USDC", token],
            "dexes": ["Jupiter", "Orca"],
            "estimated_gas": 0.001
        }
    
    def _generate_request_id(self, request: NLPRequest) -> str:
        """Generate unique request ID"""
        data = f"{request.text}:{request.user_id}:{datetime.now().isoformat()}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]
    
    async def _get_cached_response(self, request_id: str) -> Optional[NLPResponse]:
        """Get cached response if available"""
        if not self.cache:
            return None
            
        cached = self.cache.get(f"nlp:response:{request_id}")
        if cached:
            return NLPResponse(**json.loads(cached))
        return None
    
    async def _cache_response(self, request_id: str, response: NLPResponse):
        """Cache response with TTL"""
        if not self.cache:
            return
            
        self.cache.setex(
            f"nlp:response:{request_id}",
            timedelta(minutes=5),
            json.dumps(response.dict())
        )
    
    def _log_metrics(self, request: NLPRequest, response: NLPResponse):
        """Log metrics for monitoring"""
        metrics = {
            "request_id": response.request_id,
            "intent_type": response.intent.type,
            "processing_time": response.processing_time,
            "confidence": response.intent.confidence,
            "user_id": request.user_id,
            "timestamp": datetime.now().isoformat()
        }
        
        logger.info("NLP metrics", extra=metrics)

    async def _handle_analysis_intent(self, request: NLPRequest) -> Dict[str, Any]:
        """Handle analysis intent"""
        return {
            "type": "technical" if "technical" in request.text.lower() else "fundamental",
            "metrics": ["price", "volume", "market_cap"],
            "timeframe": "24h"
        }
    
    async def _handle_monitor_intent(self, request: NLPRequest) -> Dict[str, Any]:
        """Handle monitoring intent"""
        return {
            "metrics": ["price", "volume", "tps"],
            "interval": "1m",
            "alerts": True
        }
    
    async def _handle_stake_intent(self, request: NLPRequest) -> Dict[str, Any]:
        """Handle staking intent"""
        return {
            "type": "stake",
            "duration": "flexible",
            "rewards": "auto_compound"
        }
    
    async def _generate_trade_suggestions(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Generate trade suggestions based on parameters"""
        suggestions = {
            "safety": [
                "Consider setting a stop loss",
                "Verify token contract address",
                f"Current slippage is set to {params.get('smart_slippage', 0.5)}%"
            ],
            "alternatives": [
                "You can use limit orders for better price execution",
                "Consider dollar-cost averaging for large trades",
                "Check multiple DEXes for better prices"
            ]
        }
        
        if params.get('amount', 0) > 100:
            suggestions["safety"].append("This is a large trade, consider splitting it")
        
        return suggestions
    
    async def _generate_analysis_suggestions(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Generate analysis suggestions"""
        return {
            "safety": [
                "Always verify data sources",
                "Consider multiple timeframes",
                "Check market correlation"
            ],
            "alternatives": [
                "Try technical analysis",
                "Look at on-chain metrics",
                "Consider social sentiment"
            ]
        }
    
    async def _generate_stake_suggestions(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Generate staking suggestions"""
        return {
            "safety": [
                "Verify staking contract",
                "Check unstaking period",
                "Understand risks"
            ],
            "alternatives": [
                "Consider liquid staking",
                "Look at different validators",
                "Compare APY rates"
            ]
        }
    
    async def _assess_trade_risk(self, params: Dict[str, Any], request: NLPRequest) -> Dict[str, Any]:
        """Assess trading risks"""
        return {
            "risk_level": "medium",
            "factors": [
                "Token liquidity",
                "Market volatility",
                "Transaction size"
            ],
            "recommendations": [
                "Use MEV protection",
                "Set appropriate slippage",
                "Monitor execution"
            ]
        }
    
    async def _assess_stake_risk(self, params: Dict[str, Any], request: NLPRequest) -> Dict[str, Any]:
        """Assess staking risks"""
        return {
            "risk_level": "low",
            "factors": [
                "Validator reputation",
                "Staking conditions",
                "Network stability"
            ],
            "recommendations": [
                "Diversify validators",
                "Monitor performance",
                "Keep some tokens liquid"
            ]
        } 