"""
Hyperliquid Trading Module with Builder Codes
Handles real Hyperliquid trading with proper builder code integration
"""

import logging
import os
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass
from decimal import Decimal

logger = logging.getLogger(__name__)

@dataclass
class TradeResult:
    """Result of a trading operation"""
    success: bool
    order_id: Optional[str] = None
    symbol: Optional[str] = None
    side: Optional[str] = None
    size: Optional[float] = None
    price: Optional[float] = None
    builder_fee_applied: bool = False
    error_message: Optional[str] = None
    raw_response: Optional[Dict[str, Any]] = None
    transaction_hash: Optional[str] = None

@dataclass
class MarketData:
    """Market data for a symbol"""
    symbol: str
    price: float
    volume_24h: float
    change_24h: float
    available: bool = True

class HyperliquidTrader:
    """Handles Hyperliquid trading with builder codes"""
    
    def __init__(self, private_key: str, rpc_url: str = "https://api.hyperliquid.xyz"):
        """Initialize Hyperliquid trader"""
        self.private_key = private_key
        self.rpc_url = rpc_url
        # Builder address will be set after wallet initialization
        self.builder_address = None
        self.builder_fee_tenths_bps = 50  # 0.5 basis points
        
        # Initialize Hyperliquid components
        self._init_hyperliquid()
    
    def _init_hyperliquid(self):
        """Initialize Hyperliquid SDK components"""
        try:
            from hyperliquid.info import Info
            from hyperliquid.exchange import Exchange
            from hyperliquid.utils import constants
            from eth_account import Account
            
            # Initialize account
            self.account = Account.from_key(self.private_key)
            self.wallet_address = self.account.address
            # Set builder address to YOUR wallet address (you earn the fees)
            self.builder_address = "0x292F0E22A0245387a89d5DB50F016d18D6aF0bac"
            
            # Initialize Info and Exchange
            self.info = Info(constants.MAINNET_API_URL, skip_ws=True)
            self.exchange = Exchange(
                self.account,
                constants.MAINNET_API_URL,
                account_address=self.wallet_address
            )
            
            logger.info(f"Hyperliquid trader initialized for {self.wallet_address}")
            
        except Exception as e:
            logger.error(f"Failed to initialize Hyperliquid: {e}")
            self.info = None
            self.exchange = None
            self.account = None
            self.wallet_address = None
    
    async def get_market_data(self, symbol: str) -> Optional[MarketData]:
        """Get current market data for a symbol"""
        try:
            if not self.info:
                return None
            
            # Get all market data
            all_mids = self.info.all_mids()
            if not isinstance(all_mids, dict):
                return None
            
            price = all_mids.get(symbol)
            if not price:
                return None
            
            # Get additional market info
            meta = self.info.meta()
            if isinstance(meta, dict) and "universe" in meta:
                universe = meta["universe"]
                for asset in universe:
                    if asset.get("name") == symbol:
                        return MarketData(
                            symbol=symbol,
                            price=float(price),
                            volume_24h=float(asset.get("volume24h", 0)),
                            change_24h=float(asset.get("change24h", 0)),
                            available=True
                        )
            
            return MarketData(
                symbol=symbol,
                price=float(price),
                volume_24h=0.0,
                change_24h=0.0,
                available=True
            )
            
        except Exception as e:
            logger.error(f"Failed to get market data for {symbol}: {e}")
            return None
    
    async def get_asset_info(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get asset information including tick sizes"""
        try:
            if not self.info:
                return None
            
            meta = self.info.meta()
            if isinstance(meta, dict) and "universe" in meta:
                universe = meta["universe"]
                for asset in universe:
                    if asset.get("name") == symbol:
                        return asset
            return None
        except Exception as e:
            logger.error(f"Failed to get asset info for {symbol}: {e}")
            return None
    
    def round_to_tick_size(self, price: float, tick_sz: str) -> float:
        """Round price to valid tick size"""
        try:
            tick_size = float(tick_sz)
            if tick_size <= 0:
                return price
            return round(price / tick_size) * tick_size
        except:
            return price
    
    def round_size_to_lot_size(self, size: float, sz_decimals: int) -> float:
        """Round size to valid lot size based on decimals"""
        try:
            if sz_decimals <= 0:
                return round(size)
            return round(size, sz_decimals)
        except:
            return size

    async def place_trade(self, symbol: str, side: str, size: float, 
                         is_reduce_only: bool = False) -> TradeResult:
        """
        Place a trade with builder code according to Hyperliquid docs
        
        Args:
            symbol: Trading symbol (e.g., 'BTC')
            side: 'BUY' or 'SELL'
            size: Position size
            is_reduce_only: Whether this is a reduce-only order
            
        Returns:
            TradeResult with trade details
        """
        try:
            if not self.exchange:
                return TradeResult(
                    success=False,
                    error_message="Hyperliquid exchange not initialized"
                )
            
            # Get current market price
            market_data = await self.get_market_data(symbol)
            if not market_data:
                return TradeResult(
                    success=False,
                    error_message=f"Market data not available for {symbol}"
                )
            
            # Get asset info for tick size validation
            asset_info = await self.get_asset_info(symbol)
            if not asset_info:
                logger.warning(f"Could not get asset info for {symbol}, proceeding without validation")
            
            # Validate trade parameters
            if side.upper() not in ['BUY', 'SELL']:
                return TradeResult(
                    success=False,
                    error_message="Side must be 'BUY' or 'SELL'"
                )
            
            if size <= 0:
                return TradeResult(
                    success=False,
                    error_message="Size must be positive"
                )
            
            # Round size to valid lot size if we have asset info
            original_size = size
            if asset_info:
                sz_decimals = asset_info.get("szDecimals", 3)  # Default to 3 decimals
                size = self.round_size_to_lot_size(size, sz_decimals)
                logger.info(f"Rounded size from {original_size} to {size} (decimals: {sz_decimals})")
            
            # Round price to valid tick size if we have asset info
            current_price = market_data.price
            if asset_info:
                tick_sz = asset_info.get("tickSz", "0.01")  # Default tick size
                rounded_price = self.round_to_tick_size(current_price, tick_sz)
                logger.info(f"Rounded price from {current_price} to {rounded_price} (tick: {tick_sz})")
                current_price = rounded_price
            
            # Place order with proper Hyperliquid API format
            # According to docs: https://hyperliquid.gitbook.io/hyperliquid-docs/trading/builder-codes
            is_buy = side.upper() == 'BUY'
            limit_px = str(current_price)  # Use rounded price
            sz = str(size)  # Use rounded size
            
            # Place order with proper Hyperliquid API format
            # According to docs: https://hyperliquid.gitbook.io/hyperliquid-docs/trading/builder-codes
            builder_info = {
                "b": self.builder_address,
                "f": self.builder_fee_tenths_bps
            }
            
            result = self.exchange.order(
                symbol.upper(),
                is_buy,
                float(sz),
                float(limit_px),
                {"limit": {"tif": "Ioc"}},
                builder=builder_info
            )
            
            # Debug: Log the actual response
            logger.info(f"Hyperliquid order response: {result} (type: {type(result)})")
            
            # Handle different response formats
            if isinstance(result, dict):
                if result.get("status") == "ok":
                    # Check for actual errors in the response data
                    response_data = result.get("response", {})
                    data = response_data.get("data", {})
                    statuses = data.get("statuses", [])
                    
                    # Check if there are any errors in statuses
                    if statuses and any(status.get("error") for status in statuses):
                        error_msgs = [status.get("error") for status in statuses if status.get("error")]
                        logger.warning(f"Trade failed with errors: {error_msgs}")
                        return TradeResult(
                            success=False,
                            error_message=f"Trade failed: {'; '.join(error_msgs)}",
                            symbol=symbol,
                            side=side.upper(),
                            size=size,
                            price=market_data.price,
                            raw_response=result
                        )
                    else:
                        logger.info(f"Trade placed successfully: {symbol} {side} {size}")
                        return TradeResult(
                            success=True,
                            order_id=data.get("oid"),
                            symbol=symbol,
                            side=side.upper(),
                            size=size,  # This is the rounded size
                            price=current_price,  # This is the rounded price
                            builder_fee_applied=True,
                            raw_response=result
                        )
                else:
                    # Handle error response - response can be string or dict
                    response = result.get("response", "Unknown error")
                    if isinstance(response, dict):
                        error_msg = response.get("error", "Unknown error")
                    else:
                        error_msg = str(response)
                    return TradeResult(
                        success=False,
                        error_message=f"Trade failed: {error_msg}"
                    )
            elif isinstance(result, str):
                # Sometimes Hyperliquid returns a string response
                if "ok" in result.lower() or "success" in result.lower():
                    logger.info(f"Trade placed successfully: {symbol} {side} {size}")
                    return TradeResult(
                        success=True,
                        order_id="unknown",
                        symbol=symbol,
                        side=side.upper(),
                        size=size,
                        price=market_data.price,
                        builder_fee_applied=True
                    )
                else:
                    return TradeResult(
                        success=False,
                        error_message=f"Trade failed: {result}"
                    )
            else:
                # Unexpected response format
                logger.warning(f"Unexpected response format: {type(result)} - {result}")
                return TradeResult(
                    success=False,
                    error_message=f"Unexpected response format: {result}"
                )
                
        except Exception as e:
            logger.error(f"Trade execution failed: {e}")
            return TradeResult(
                success=False,
                error_message=f"Trade execution failed: {str(e)}"
            )
    
    async def check_builder_approval(self, wallet_address: str) -> bool:
        """Check if user has approved builder fees using correct API"""
        try:
            if not self.info:
                return False
            
            # Use the correct info request format as per Hyperliquid docs
            # {"type": "maxBuilderFee", "user": "0x...", "builder": "0x..."}
            info_request = {
                "type": "maxBuilderFee",
                "user": wallet_address,
                "builder": self.builder_address
            }
            
            # Make the info request
            response = self.info.post(info_request)
            
            # Debug the response format
            logger.info(f"Builder approval response: {response} (type: {type(response)})")
            
            # Handle different response formats
            if response is None:
                logger.info("No builder approval found (None response)")
                return False
            elif isinstance(response, dict):
                # Response might be a dict with error or data
                if "error" in response:
                    logger.info(f"Builder approval error: {response['error']}")
                    return False
                # Extract approval value from dict if present
                approval_value = response.get("approval", response.get("value", response.get("maxBuilderFee", 0)))
                if isinstance(approval_value, (int, float)) and approval_value > 0:
                    logger.info(f"Builder approval found: {approval_value} tenths of basis points")
                    return True
                else:
                    logger.info(f"No builder approval found in dict response: {response}")
                    return False
            elif isinstance(response, (int, float)):
                # Response is a number
                if response > 0:
                    logger.info(f"Builder approval found: {response} tenths of basis points")
                    return True
                else:
                    logger.info("No builder approval found (0 value)")
                    return False
            else:
                logger.info(f"Unexpected response format: {type(response)} - {response}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to check builder approval: {str(e)}")
            return False

    async def approve_builder_fee(self, wallet_address: str, private_key: str) -> bool:
        """Approve builder fees using Hyperliquid SDK exactly as in example_utils.py"""
        try:
            if not self.exchange:
                logger.error("Exchange not initialized")
                return False
            
            # Check if this is the main wallet (not API wallet) - exactly as in example
            if self.exchange.account_address != self.exchange.wallet.address:
                logger.error("Only the main wallet has permission to approve a builder fee")
                return False
            
            # Approve builder fee using SDK method exactly as in example_utils.py
            # Format: exchange.approve_builder_fee(builder_address, fee_percentage)
            approve_result = self.exchange.approve_builder_fee(
                self.builder_address, 
                "0.005%"  # 0.5 basis points (0.005%)
            )
            
            logger.info(f"Builder fee approval result: {approve_result}")
            return True
                
        except Exception as e:
            logger.error(f"Failed to approve builder fee: {e}")
            return False

    async def _get_asset_id(self, symbol: str) -> Optional[int]:
        """Get asset ID for symbol"""
        try:
            if not self.info:
                return None
            
            meta = self.info.meta()
            if isinstance(meta, dict) and "universe" in meta:
                universe = meta["universe"]
                logger.info(f"Available symbols: {[asset.get('name') for asset in universe[:10]]}")
                
                for i, asset in enumerate(universe):
                    asset_name = asset.get("name", "").upper()
                    if asset_name == symbol.upper():
                        logger.info(f"Found asset {symbol} at index {i}")
                        return i
                    
                    # If not found, try common variations
                    symbol_variations = [symbol.upper(), f"{symbol.upper()}-PERP", f"{symbol.upper()}-USD"]
                    for variation in symbol_variations:
                        for i, asset in enumerate(universe):
                            asset_name = asset.get("name", "").upper()
                            if asset_name == variation:
                                logger.info(f"Found asset {variation} at index {i}")
                                return i
                                
                logger.warning(f"Asset {symbol} not found in universe")
                return None
                
        except Exception as e:
            logger.error(f"Failed to get asset ID for {symbol}: {e}")
            return None
    
    async def get_account_balance(self) -> Dict[str, Any]:
        """Get account balance and positions"""
        try:
            if not self.info or not self.wallet_address:
                return {"error": "Hyperliquid not initialized"}
            
            # Get user state
            user_state = self.info.user_state(self.wallet_address)
            
            if not user_state:
                return {"error": "Unable to fetch account state"}
            
            # Extract balance information
            margin_summary = user_state.get("marginSummary", {})
            account_value = float(margin_summary.get("accountValue", 0))
            total_margin_used = float(margin_summary.get("totalMarginUsed", 0))
            total_ntl_pos = float(margin_summary.get("totalNtlPos", 0))
            
            # Get positions
            positions = []
            asset_positions = user_state.get("assetPositions", [])
            for pos in asset_positions:
                position = pos.get("position", {})
                if position:
                    positions.append({
                        "coin": position.get("coin", ""),
                        "szi": float(position.get("szi", 0)),
                        "entry_px": float(position.get("entryPx", 0)),
                        "position_value": float(position.get("positionValue", 0)),
                        "unrealized_pnl": float(position.get("unrealizedPnl", 0))
                    })
            
            return {
                "account_value": account_value,
                "total_margin_used": total_margin_used,
                "total_ntl_pos": total_ntl_pos,
                "available_balance": account_value - total_margin_used,
                "positions": positions,
                "wallet_address": self.wallet_address
            }
            
        except Exception as e:
            logger.error(f"Failed to get account balance: {e}")
            return {"error": f"Failed to get balance: {str(e)}"}
    
    async def get_open_orders(self) -> list:
        """Get open orders"""
        try:
            if not self.info or not self.wallet_address:
                return []
            
            # Get open orders
            open_orders = self.info.open_orders(self.wallet_address)
            
            if not isinstance(open_orders, list):
                return []
            
            return open_orders
            
        except Exception as e:
            logger.error(f"Failed to get open orders: {e}")
            return []
    
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an open order"""
        try:
            if not self.exchange:
                return False
            
            # Cancel order
            result = self.exchange.cancel(order_id)
            
            return result.get("status") == "ok"
            
        except Exception as e:
            logger.error(f"Failed to cancel order {order_id}: {e}")
            return False
    
    def get_builder_code_info(self) -> Dict[str, Any]:
        """Get builder code information"""
        return {
            "builder_address": self.builder_address,
            "fee_tenths_bps": self.builder_fee_tenths_bps,
            "fee_percentage": self.builder_fee_tenths_bps / 10000,
            "description": "Hyperliquid Builder Code for automated trading"
        }
    
    async def validate_symbol(self, symbol: str) -> bool:
        """Validate if symbol is tradeable"""
        try:
            market_data = await self.get_market_data(symbol)
            return market_data is not None and market_data.available
        except:
            return False
