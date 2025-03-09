"""
Odos Service
Integrates Odos agent for optimal DeFi swaps and routing
"""

import logging
import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field

from src.agents.odos_agent import OdosAgent, SwapRequest, TokenAmount
from src.core.market_data import MarketDataService
from src.core.risk_analyzer import RiskAnalyzer

logger = logging.getLogger(__name__)

class OdosSwapRequest(BaseModel):
    """User-facing model for swap requests"""
    user_address: str
    from_token: str  # Token address or symbol
    to_token: str    # Token address or symbol
    amount: str      # Amount in token's smallest unit (e.g., wei for ETH)
    slippage: float = Field(0.5, ge=0.01, le=10.0)  # Between 0.01% and 10%
    chain_id: int = 1  # Default to Ethereum mainnet
    referrer: Optional[str] = None

class SwapResult(BaseModel):
    """Model for swap execution results"""
    success: bool
    input_token: Dict[str, Any]
    output_token: Dict[str, Any]
    estimated_gas: str
    price_impact: float
    transaction_hash: Optional[str] = None
    error: Optional[str] = None
    timestamp: datetime

class OdosService:
    """Service for managing Odos Protocol interactions"""
    
    def __init__(self):
        # Initialize the agent
        self.odos_agent = OdosAgent()
        # Market data for price checks and token information
        self.market_data = MarketDataService()
        # Risk analyzer for transaction safety
        self.risk_analyzer = RiskAnalyzer()
        
        # Token address cache (symbol -> address mapping)
        self._token_cache = {}
        
    async def close(self):
        """Close connections when service is done"""
        await self.odos_agent.close()
    
    async def get_token_address(self, token_symbol_or_address: str, chain_id: int = 1) -> str:
        """
        Get token address from symbol or return the address if it's already an address.
        Caches results for faster lookup.
        """
        # If it looks like an address, return it directly
        if token_symbol_or_address.startswith("0x") and len(token_symbol_or_address) == 42:
            return token_symbol_or_address
            
        # Check cache first
        cache_key = f"{token_symbol_or_address.upper()}_{chain_id}"
        if cache_key in self._token_cache:
            return self._token_cache[cache_key]
            
        # Get supported tokens
        tokens = await self.odos_agent.get_supported_tokens(chain_id)
        
        # Find token by symbol (case insensitive)
        symbol_upper = token_symbol_or_address.upper()
        for token in tokens:
            if token.get("symbol", "").upper() == symbol_upper:
                address = token.get("address")
                if address:
                    # Cache the result
                    self._token_cache[cache_key] = address
                    return address
                    
        # If not found, attempt to get from market data service
        try:
            token_data = await self.market_data.get_token_data(token_symbol_or_address)
            if token_data and "address" in token_data:
                address = token_data["address"]
                # Cache the result
                self._token_cache[cache_key] = address
                return address
        except Exception as e:
            logger.warning(f"Error getting token data from market service: {str(e)}")
            
        # If we still don't have it, raise an error
        raise ValueError(f"Token not found: {token_symbol_or_address} on chain_id {chain_id}")
    
    async def get_swap_quote(self, request: OdosSwapRequest) -> Dict[str, Any]:
        """
        Get a quote for a token swap using Odos Protocol.
        Converts from user-friendly format to the format required by the Odos agent.
        """
        try:
            # Resolve token addresses
            from_token_address = await self.get_token_address(request.from_token, request.chain_id)
            to_token_address = await self.get_token_address(request.to_token, request.chain_id)
            
            # Create agent request
            swap_request = SwapRequest(
                input_token=TokenAmount(
                    token_address=from_token_address,
                    amount=request.amount
                ),
                output_token=TokenAmount(
                    token_address=to_token_address,
                    amount="0"  # We don't know the output amount yet
                ),
                slippage_tolerance_percentage=request.slippage,
                user_address=request.user_address,
                chain_id=request.chain_id,
                referrer_address=request.referrer
            )
            
            # Get the quote
            swap_details = await self.odos_agent.get_swap_details(swap_request)
            
            # Enhance with additional data
            from_token_info = await self._get_token_info(from_token_address, request.chain_id)
            to_token_info = await self._get_token_info(to_token_address, request.chain_id)
            
            swap_details["from_token"] = from_token_info
            swap_details["to_token"] = to_token_info
            
            # Add risk assessment
            risk_assessment = await self._assess_swap_risk(
                swap_details,
                from_token_info,
                to_token_info
            )
            swap_details["risk_assessment"] = risk_assessment
            
            return swap_details
            
        except Exception as e:
            logger.error(f"Error getting swap quote: {str(e)}")
            return {"error": str(e)}
    
    async def _get_token_info(self, token_address: str, chain_id: int) -> Dict[str, Any]:
        """
        Get detailed token information.
        Combines data from Odos and market data service.
        """
        token_info = {"address": token_address}
        
        try:
            # Try to get from Odos supported tokens first
            tokens = await self.odos_agent.get_supported_tokens(chain_id)
            for token in tokens:
                if token.get("address", "").lower() == token_address.lower():
                    token_info.update({
                        "symbol": token.get("symbol"),
                        "name": token.get("name"),
                        "decimals": token.get("decimals")
                    })
                    break
                    
            # Enhance with market data if available
            if "symbol" in token_info:
                market_data = await self.market_data.get_token_data(token_info["symbol"])
                if market_data:
                    token_info["price_usd"] = market_data.get("price_usd")
                    token_info["volume_24h"] = market_data.get("volume_24h")
                    token_info["market_cap"] = market_data.get("market_cap")
                    
            return token_info
            
        except Exception as e:
            logger.warning(f"Error getting token info: {str(e)}")
            return token_info
    
    async def _assess_swap_risk(self, 
                               swap_details: Dict[str, Any],
                               from_token: Dict[str, Any],
                               to_token: Dict[str, Any]) -> Dict[str, Any]:
        """
        Assess the risk of the swap transaction.
        """
        try:
            # Extract relevant data
            amount_in_usd = 0
            price_impact = swap_details.get("price_impact_percentage", 0)
            
            # Calculate amount in USD if price is available
            if "price_usd" in from_token:
                token_price = from_token["price_usd"]
                token_amount = float(swap_details["quote"]["input_token"]["amount"])
                token_decimals = from_token.get("decimals", 18)
                amount_in_usd = token_price * (token_amount / (10 ** token_decimals))
            
            # Get risk assessment from risk analyzer
            risk_data = {
                "token_in": from_token.get("symbol", from_token["address"]),
                "token_out": to_token.get("symbol", to_token["address"]),
                "amount_usd": amount_in_usd,
                "price_impact": price_impact
            }
            
            risk_assessment = await self.risk_analyzer.analyze_trade_risk(**risk_data)
            return risk_assessment
            
        except Exception as e:
            logger.warning(f"Error in risk assessment: {str(e)}")
            return {
                "risk_level": "unknown",
                "warning": "Unable to assess risk",
                "details": str(e)
            }
    
    async def list_supported_tokens(self, chain_id: int = 1) -> List[Dict[str, Any]]:
        """
        Get a list of all supported tokens with enhanced information.
        """
        try:
            tokens = await self.odos_agent.get_supported_tokens(chain_id)
            
            # Add additional information for common tokens
            enhanced_tokens = []
            for token in tokens:
                token_data = token.copy()
                
                # Try to get market data if symbol is available
                if "symbol" in token:
                    try:
                        market_info = await self.market_data.get_token_data(token["symbol"])
                        if market_info:
                            token_data.update({
                                "price_usd": market_info.get("price_usd"),
                                "volume_24h": market_info.get("volume_24h"),
                                "market_cap": market_info.get("market_cap"),
                                "change_24h": market_info.get("change_24h")
                            })
                    except Exception as e:
                        logger.debug(f"Could not get market data for {token['symbol']}: {str(e)}")
                
                enhanced_tokens.append(token_data)
                
            return enhanced_tokens
            
        except Exception as e:
            logger.error(f"Error listing supported tokens: {str(e)}")
            return []
    
    async def get_swap_routes(self, request: OdosSwapRequest) -> Dict[str, Any]:
        """
        Get detailed routing information for a swap.
        Shows all the exchanges and pools that will be used.
        """
        try:
            # First get the swap quote
            swap_details = await self.get_swap_quote(request)
            
            if "error" in swap_details:
                return swap_details
                
            # Extract route information
            path_id = swap_details["quote"]["path_id"]
            
            # Get full path details from Odos API (this is a hypothetical endpoint)
            # In a real implementation, you'd need to check if Odos has this endpoint
            # or if you need to parse the transaction data to extract route info
            route_info = await self._extract_route_info(swap_details)
            
            return {
                "from_token": swap_details["from_token"],
                "to_token": swap_details["to_token"],
                "amount_in": swap_details["quote"]["input_token"]["amount"],
                "amount_out": swap_details["quote"]["output_token"]["amount"],
                "path_id": path_id,
                "route": route_info,
                "gas_estimate": swap_details["quote"]["gas_estimate_wei"],
                "price_impact": swap_details["price_impact_percentage"]
            }
            
        except Exception as e:
            logger.error(f"Error getting swap routes: {str(e)}")
            return {"error": str(e)}
    
    async def _extract_route_info(self, swap_details: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract routing information from swap details.
        This is just a placeholder as the actual implementation would depend on
        what information Odos provides about routes.
        """
        # In a real implementation, you'd parse transaction data or call a dedicated API
        # For now, we'll return a placeholder with the information we know
        return [
            {
                "protocol": "Odos Smart Order Router",
                "portion": 100,  # 100% routed through Odos
                "from_token": swap_details["from_token"]["symbol"] if "symbol" in swap_details["from_token"] else swap_details["from_token"]["address"],
                "to_token": swap_details["to_token"]["symbol"] if "symbol" in swap_details["to_token"] else swap_details["to_token"]["address"],
                "path_id": swap_details["quote"]["path_id"]
            }
        ] 