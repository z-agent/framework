"""
Odos Agent for DeFi Integrations
Implements functionality for interacting with Odos Protocol for optimal swaps and liquidity routing
"""

import logging
import os
import json
import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel
import httpx

from src.utils.rate_limiter import rate_limiter
from src.utils.cache_manager import cache_manager
from src.utils.error_handler import handle_api_error

logger = logging.getLogger(__name__)

class TokenAmount(BaseModel):
    """Model for token amount information"""
    token_address: str
    amount: str  # String representation of a number to avoid precision loss
    
class SwapRequest(BaseModel):
    """Model for swap request parameters"""
    input_token: TokenAmount
    output_token: TokenAmount
    slippage_tolerance_percentage: float = 0.5
    gas_price_wei: Optional[str] = None
    disable_estimates: bool = False
    referrer_address: Optional[str] = None
    user_address: str
    chain_id: int = 1  # Default to Ethereum mainnet

class SwapPathInfo(BaseModel):
    """Model for detailed swap path information"""
    path_id: str
    input_token: TokenAmount
    output_token: TokenAmount
    exchange_route: List[Dict[str, Any]]
    gas_estimate_wei: str
    quote_timestamp: datetime
    price_impact: float
    
class SwapQuote(BaseModel):
    """Model for swap quotes"""
    path_id: str
    input_token: TokenAmount
    output_token: TokenAmount
    gas_estimate_wei: str
    quote_timestamp: datetime
    price_impact: float
    transaction_data: Optional[Dict[str, Any]] = None
    
class OdosAgent:
    """Agent for interacting with Odos Protocol"""
    
    def __init__(self, api_key: Optional[str] = None, base_url: str = "https://api.odos.xyz"):
        """Initialize the Odos agent with API credentials."""
        self.api_key = api_key or os.getenv("ODOS_API_KEY")
        self.base_url = base_url
        self.cache = cache_manager
        
        # Configure the HTTP client with authentication headers
        self.http_client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}" if self.api_key else ""
            },
            timeout=30.0  # 30 seconds timeout
        )
        
    async def close(self):
        """Close the HTTP client when done."""
        await self.http_client.aclose()
    
    @rate_limiter(max_calls=10, period=1)  # Limit to 10 calls per second
    async def get_quote(self, swap_request: SwapRequest) -> SwapQuote:
        """
        Get a quote for a token swap using Odos Protocol.
        Rate limited to prevent API abuse.
        """
        cache_key = f"odos_quote_{swap_request.input_token.token_address}_{swap_request.input_token.amount}_{swap_request.output_token.token_address}_{swap_request.chain_id}"
        
        # Check cache first (with short TTL since prices change frequently)
        cached_result = await self.cache.get(cache_key)
        if cached_result:
            logger.debug(f"Using cached quote for {cache_key}")
            return SwapQuote(**cached_result)
        
        try:
            # Convert request to Odos API format
            payload = {
                "chainId": swap_request.chain_id,
                "inputTokens": [{
                    "tokenAddress": swap_request.input_token.token_address,
                    "amount": swap_request.input_token.amount
                }],
                "outputTokens": [{
                    "tokenAddress": swap_request.output_token.token_address,
                    "proportion": 1  # 100% of the output
                }],
                "slippageLimitPercent": swap_request.slippage_tolerance_percentage,
                "userAddr": swap_request.user_address,
                "referrerAddr": swap_request.referrer_address,
                "disableEstimates": swap_request.disable_estimates
            }
            
            if swap_request.gas_price_wei:
                payload["gasPrice"] = swap_request.gas_price_wei
            
            # Get the quote from Odos API
            response = await self.http_client.post("/sor/quote", json=payload)
            response.raise_for_status()
            quote_data = response.json()
            
            # Convert to our model format
            result = SwapQuote(
                path_id=quote_data["pathId"],
                input_token=TokenAmount(
                    token_address=swap_request.input_token.token_address,
                    amount=swap_request.input_token.amount
                ),
                output_token=TokenAmount(
                    token_address=swap_request.output_token.token_address,
                    amount=quote_data["outputTokens"][0]["amount"]
                ),
                gas_estimate_wei=quote_data.get("gasEstimate", "0"),
                quote_timestamp=datetime.utcnow(),
                price_impact=quote_data.get("priceImpact", 0.0)
            )
            
            # Cache the result (short TTL since prices change quickly)
            await self.cache.set(cache_key, result.dict(), ttl=30)  # 30 seconds cache
            return result
            
        except Exception as e:
            error_msg = f"Error getting Odos quote: {str(e)}"
            logger.error(error_msg)
            handle_api_error("odos_get_quote", error_msg, swap_request.dict())
            raise
    
    @rate_limiter(max_calls=5, period=1)  # More conservative rate limiting
    async def assemble_transaction(self, path_id: str, user_address: str, chain_id: int = 1) -> Dict[str, Any]:
        """
        Assemble a transaction using a previously obtained path_id.
        Rate limited more conservatively since it's a transaction creation endpoint.
        """
        cache_key = f"odos_tx_{path_id}_{user_address}_{chain_id}"
        
        # Check cache (very short TTL since transaction data should be fresh)
        cached_result = await self.cache.get(cache_key)
        if cached_result:
            logger.debug(f"Using cached transaction for {path_id}")
            return cached_result
        
        try:
            # Build the request
            payload = {
                "userAddr": user_address,
                "pathId": path_id,
                "chainId": chain_id
            }
            
            # Get transaction data from Odos API
            response = await self.http_client.post("/sor/assemble", json=payload)
            response.raise_for_status()
            transaction_data = response.json()
            
            # Cache the result (very short TTL)
            await self.cache.set(cache_key, transaction_data, ttl=15)  # 15 seconds cache
            return transaction_data
            
        except Exception as e:
            error_msg = f"Error assembling Odos transaction: {str(e)}"
            logger.error(error_msg)
            handle_api_error("odos_assemble_tx", error_msg, {"path_id": path_id, "user_address": user_address})
            raise
    
    async def get_supported_tokens(self, chain_id: int = 1) -> List[Dict[str, Any]]:
        """
        Get a list of tokens supported by Odos for a specific chain.
        Result is cached for longer periods since token lists change infrequently.
        """
        cache_key = f"odos_tokens_{chain_id}"
        
        # Check longer cache for token lists
        cached_result = await self.cache.get(cache_key)
        if cached_result:
            return cached_result
        
        try:
            response = await self.http_client.get(f"/info/tokens?chainId={chain_id}")
            response.raise_for_status()
            tokens = response.json()
            
            # Cache the token list for longer (tokens don't change often)
            await self.cache.set(cache_key, tokens, ttl=3600)  # 1 hour cache
            return tokens
            
        except Exception as e:
            error_msg = f"Error getting Odos supported tokens: {str(e)}"
            logger.error(error_msg)
            handle_api_error("odos_supported_tokens", error_msg, {"chain_id": chain_id})
            return []
    
    async def simulate_swap(self, transaction_data: Dict[str, Any], chain_id: int = 1) -> Dict[str, Any]:
        """
        Simulate a swap transaction before executing it.
        Important for validation and gas estimation.
        """
        try:
            payload = {
                "transaction": transaction_data,
                "chainId": chain_id
            }
            
            response = await self.http_client.post("/sor/simulate", json=payload)
            response.raise_for_status()
            return response.json()
            
        except Exception as e:
            error_msg = f"Error simulating Odos transaction: {str(e)}"
            logger.error(error_msg)
            handle_api_error("odos_simulate", error_msg, {"chain_id": chain_id})
            return {"success": False, "error": str(e)}
    
    async def get_swap_details(self, swap_request: SwapRequest) -> Dict[str, Any]:
        """
        Get complete swap details including quote, gas estimates, and price impact.
        This is a high-level method that combines multiple API calls.
        """
        try:
            # First get the quote
            quote = await self.get_quote(swap_request)
            
            # Then assemble the transaction
            transaction = await self.assemble_transaction(
                quote.path_id, 
                swap_request.user_address,
                swap_request.chain_id
            )
            
            # Combine the results
            return {
                "quote": quote.dict(),
                "transaction": transaction,
                "estimated_output": quote.output_token.amount,
                "price_impact_percentage": quote.price_impact * 100,  # Convert to percentage
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            error_msg = f"Error getting complete swap details: {str(e)}"
            logger.error(error_msg)
            handle_api_error("odos_swap_details", error_msg, swap_request.dict())
            return {"error": str(e)} 