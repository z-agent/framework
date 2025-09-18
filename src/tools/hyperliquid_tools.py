#!/usr/bin/env python3
"""
🚀 HYPERLIQUID INTEGRATION TOOLS
Builder code integration for earning fees on trades
Perfect integration with Zara Framework's existing trading capabilities
"""

import os
import requests
import hashlib
import hmac
import time
import json
from typing import Dict, Any, Optional, List
from crewai.tools import BaseTool
from pydantic import Field, BaseModel
from eth_account import Account
from eth_account.messages import encode_defunct
import pandas as pd

# Hyperliquid API endpoints
HYPERLIQUID_API_BASE = "https://api.hyperliquid.xyz"
HYPERLIQUID_INFO_URL = f"{HYPERLIQUID_API_BASE}/info"
HYPERLIQUID_EXCHANGE_URL = f"{HYPERLIQUID_API_BASE}/exchange"

class HyperliquidConfig:
    """Configuration for Hyperliquid API"""
    
    def __init__(self):
        self.private_key = os.getenv('HYPERLIQUID_PRIVATE_KEY')
        self.builder_address = os.getenv('HYPERLIQUID_BUILDER_ADDRESS')
        self.default_builder_fee = int(os.getenv('HYPERLIQUID_BUILDER_FEE', '5'))  # 0.5 basis points default
        
        if not self.private_key:
            raise ValueError("HYPERLIQUID_PRIVATE_KEY environment variable required")
        
        # Create account from private key
        self.account = Account.from_key(self.private_key)
        self.address = self.account.address
        
        # Use account address as builder if not specified
        if not self.builder_address:
            self.builder_address = self.address

class HyperliquidMarketDataSchema(BaseModel):
    """Schema for market data requests"""
    symbol: str = Field(..., description="Trading pair symbol (e.g., 'BTC', 'ETH')")
    include_orderbook: bool = Field(default=False, description="Include orderbook data")

class HyperliquidTradingSchema(BaseModel):
    """Schema for trading operations"""
    symbol: str = Field(..., description="Trading pair symbol (e.g., 'BTC', 'ETH')")
    side: str = Field(..., description="Order side: 'buy' or 'sell'")
    size: float = Field(..., description="Order size in base currency")
    price: Optional[float] = Field(None, description="Limit price (None for market order)")
    user_address: str = Field(..., description="User's wallet address for the trade")
    builder_fee_bps: int = Field(default=5, description="Builder fee in basis points (5 = 0.5 basis points)")

class HyperliquidBuilderFeeSchema(BaseModel):
    """Schema for builder fee operations"""
    user_address: str = Field(..., description="User's wallet address")
    max_fee_bps: int = Field(..., description="Maximum builder fee in basis points to approve")

class HyperliquidAPIClient:
    """Hyperliquid API client with builder code support"""
    
    def __init__(self):
        self.config = HyperliquidConfig()
    
    def _sign_request(self, data: dict, timestamp: int) -> str:
        """Sign request for Hyperliquid API"""
        message = json.dumps(data, separators=(',', ':')) + str(timestamp)
        message_hash = hashlib.sha256(message.encode()).digest()
        signature = self.config.account.unsafe_sign_hash(message_hash)
        return signature.signature.hex()
    
    def get_market_data(self, symbol: str, include_orderbook: bool = False) -> dict:
        """Get market data for a symbol"""
        try:
            # Get general market info
            info_request = {"type": "meta"}
            response = requests.post(HYPERLIQUID_INFO_URL, json=info_request)
            
            if response.status_code != 200:
                return {"success": False, "error": f"API error: {response.status_code}"}
            
            meta_data = response.json()
            
            # Find symbol in universe
            universe = meta_data.get('universe', [])
            symbol_info = None
            for asset in universe:
                if asset['name'].upper() == symbol.upper():
                    symbol_info = asset
                    break
            
            if not symbol_info:
                return {"success": False, "error": f"Symbol {symbol} not found"}
            
            # Get current price data
            price_request = {"type": "allMids"}
            price_response = requests.post(HYPERLIQUID_INFO_URL, json=price_request)
            
            result = {
                "success": True,
                "symbol": symbol.upper(),
                "symbol_info": symbol_info,
                "timestamp": pd.Timestamp.now().isoformat()
            }
            
            if price_response.status_code == 200:
                price_data = price_response.json()
                # Find price for our symbol
                for i, asset in enumerate(universe):
                    if asset['name'].upper() == symbol.upper():
                        if i < len(price_data):
                            result["current_price"] = float(price_data[i])
                        break
            
            # Get orderbook if requested
            if include_orderbook:
                book_request = {"type": "l2Book", "coin": symbol.upper()}
                book_response = requests.post(HYPERLIQUID_INFO_URL, json=book_request)
                if book_response.status_code == 200:
                    result["orderbook"] = book_response.json()
            
            return result
            
        except Exception as e:
            return {"success": False, "error": f"Market data error: {str(e)}"}
    
    def approve_builder_fee(self, user_address: str, max_fee_bps: int) -> dict:
        """Approve maximum builder fee for a user"""
        try:
            timestamp = int(time.time() * 1000)
            
            action = {
                "type": "approveBuilderFee",
                "builder": self.config.builder_address,
                "maxFee": max_fee_bps
            }
            
            signature = self._sign_request(action, timestamp)
            
            request_data = {
                "action": action,
                "nonce": timestamp,
                "signature": signature,
                "vaultAddress": None
            }
            
            response = requests.post(HYPERLIQUID_EXCHANGE_URL, json=request_data)
            
            if response.status_code == 200:
                return {
                    "success": True,
                    "message": f"Approved max builder fee of {max_fee_bps} basis points",
                    "user_address": user_address,
                    "builder_address": self.config.builder_address,
                    "max_fee_bps": max_fee_bps
                }
            else:
                return {"success": False, "error": f"API error: {response.text}"}
                
        except Exception as e:
            return {"success": False, "error": f"Builder fee approval error: {str(e)}"}
    
    def place_order_with_builder_fee(self, symbol: str, side: str, size: float, 
                                   user_address: str, price: Optional[float] = None,
                                   builder_fee_bps: int = 5) -> dict:
        """Place order with builder fee"""
        try:
            timestamp = int(time.time() * 1000)
            
            # Convert to Hyperliquid order format
            order_type = "Limit" if price else "Market"
            
            order = {
                "coin": symbol.upper(),
                "is_buy": side.lower() == "buy",
                "sz": str(size),
                "limit_px": str(price) if price else "0",
                "order_type": {"limit": {"tif": "Gtc"}} if price else {"market": {}},
                "reduce_only": False
            }
            
            action = {
                "type": "order",
                "orders": [order],
                "grouping": "na",
                "builder": {
                    "b": self.config.builder_address,
                    "f": builder_fee_bps
                }
            }
            
            signature = self._sign_request(action, timestamp)
            
            request_data = {
                "action": action,
                "nonce": timestamp,
                "signature": signature,
                "vaultAddress": None
            }
            
            response = requests.post(HYPERLIQUID_EXCHANGE_URL, json=request_data)
            
            if response.status_code == 200:
                result = response.json()
                return {
                    "success": True,
                    "order_result": result,
                    "builder_fee_bps": builder_fee_bps,
                    "estimated_builder_fee": (size * (price or 0) * builder_fee_bps) / 10000 if price else "Market order - fee calculated on fill",
                    "symbol": symbol.upper(),
                    "side": side,
                    "size": size
                }
            else:
                return {"success": False, "error": f"Order placement error: {response.text}"}
                
        except Exception as e:
            return {"success": False, "error": f"Order placement error: {str(e)}"}
    
    def get_builder_fee_status(self, user_address: str) -> dict:
        """Get builder fee status for a user"""
        try:
            request_data = {
                "type": "maxBuilderFee",
                "user": user_address,
                "builder": self.config.builder_address
            }
            
            response = requests.post(HYPERLIQUID_INFO_URL, json=request_data)
            
            if response.status_code == 200:
                max_fee = response.json()
                return {
                    "success": True,
                    "user_address": user_address,
                    "builder_address": self.config.builder_address,
                    "max_approved_fee_bps": max_fee,
                    "status": "approved" if max_fee > 0 else "not_approved"
                }
            else:
                return {"success": False, "error": f"Fee status error: {response.text}"}
                
        except Exception as e:
            return {"success": False, "error": f"Fee status error: {str(e)}"}

# Tool implementations
class HyperliquidMarketDataTool(BaseTool):
    """Get Hyperliquid market data with analysis integration"""
    name: str = "HyperliquidMarketData"
    description: str = "Get real-time market data from Hyperliquid DEX for any trading pair"
    args_schema: type[BaseModel] = HyperliquidMarketDataSchema
    
    def _run(self, symbol: str, include_orderbook: bool = False) -> dict:
        client = HyperliquidAPIClient()
        return client.get_market_data(symbol, include_orderbook)

class HyperliquidBuilderFeeTool(BaseTool):
    """Manage builder fee approvals and status"""
    name: str = "HyperliquidBuilderFee"
    description: str = "Approve builder fees and check status for earning revenue on trades"
    args_schema: type[BaseModel] = HyperliquidBuilderFeeSchema
    
    def _run(self, user_address: str, max_fee_bps: int) -> dict:
        client = HyperliquidAPIClient()
        return client.approve_builder_fee(user_address, max_fee_bps)

class HyperliquidTradingTool(BaseTool):
    """Execute trades on Hyperliquid with builder fee collection"""
    name: str = "HyperliquidTrading"
    description: str = "Place orders on Hyperliquid DEX and earn builder fees on fills"
    args_schema: type[BaseModel] = HyperliquidTradingSchema
    
    def _run(self, symbol: str, side: str, size: float, user_address: str,
             price: Optional[float] = None, builder_fee_bps: int = 5) -> dict:
        client = HyperliquidAPIClient()
        return client.place_order_with_builder_fee(
            symbol, side, size, user_address, price, builder_fee_bps
        )

class HyperliquidAnalysisSchema(BaseModel):
    """Schema for comprehensive trading analysis"""
    symbol: str = Field(..., description="Trading pair symbol (e.g., 'BTC', 'ETH')")
    include_technical: bool = Field(default=True, description="Include technical analysis")
    include_market_data: bool = Field(default=True, description="Include market data")

class HyperliquidComprehensiveAnalysisTool(BaseTool):
    """Comprehensive analysis combining Hyperliquid data with existing framework tools"""
    name: str = "HyperliquidComprehensiveAnalysis" 
    description: str = "Get comprehensive trading analysis combining Hyperliquid market data with IvishX and Z-API analysis"
    args_schema: type[BaseModel] = HyperliquidAnalysisSchema
    
    def _run(self, symbol: str, include_technical: bool = True, include_market_data: bool = True) -> dict:
        try:
            results = {
                "success": True,
                "symbol": symbol.upper(),
                "timestamp": pd.Timestamp.now().isoformat(),
                "analysis": {}
            }
            
            # Get Hyperliquid market data
            if include_market_data:
                client = HyperliquidAPIClient()
                market_data = client.get_market_data(symbol, include_orderbook=True)
                results["analysis"]["hyperliquid_market"] = market_data
            
            # Get technical analysis from existing tools if available
            if include_technical:
                try:
                    # Import and use existing trading tools
                    from src.tools.trading_tools import CombinedTechnicalAnalysis
                    combined_tool = CombinedTechnicalAnalysis()
                    technical_analysis = combined_tool._run(symbol, days=30, timeframe="7d")
                    results["analysis"]["technical_analysis"] = technical_analysis
                except ImportError:
                    results["analysis"]["technical_analysis"] = {
                        "error": "Technical analysis tools not available"
                    }
            
            # Add trading recommendation
            if include_market_data and include_technical:
                hyperliquid_data = results["analysis"].get("hyperliquid_market", {})
                technical_data = results["analysis"].get("technical_analysis", {})
                
                recommendation = self._generate_recommendation(hyperliquid_data, technical_data)
                results["recommendation"] = recommendation
            
            return results
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Comprehensive analysis error: {str(e)}",
                "symbol": symbol
            }
    
    def _generate_recommendation(self, hyperliquid_data: dict, technical_data: dict) -> dict:
        """Generate trading recommendation based on combined data"""
        recommendation = {
            "action": "HOLD",
            "confidence": 0.5,
            "reasoning": [],
            "builder_fee_opportunity": False
        }
        
        # Analyze Hyperliquid market data
        if hyperliquid_data.get("success") and "current_price" in hyperliquid_data:
            recommendation["reasoning"].append("Real-time Hyperliquid market data available")
            recommendation["builder_fee_opportunity"] = True
        
        # Analyze technical data
        technical_summary = technical_data.get("summary", {})
        if technical_summary.get("both_successful"):
            ivishx_signal = technical_summary.get("ivishx_signal", "").upper()
            if ivishx_signal in ["BUY", "STRONG_BUY"]:
                recommendation["action"] = "BUY"
                recommendation["confidence"] = min(recommendation["confidence"] + 0.3, 1.0)
                recommendation["reasoning"].append(f"IvishX signals {ivishx_signal}")
            elif ivishx_signal in ["SELL", "STRONG_SELL"]:
                recommendation["action"] = "SELL" 
                recommendation["confidence"] = min(recommendation["confidence"] + 0.3, 1.0)
                recommendation["reasoning"].append(f"IvishX signals {ivishx_signal}")
        
        return recommendation

# Export tools for registry
HYPERLIQUID_TOOLS = [
    HyperliquidMarketDataTool(),
    HyperliquidBuilderFeeTool(),
    HyperliquidTradingTool(),
    HyperliquidComprehensiveAnalysisTool()
]


