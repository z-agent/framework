#!/usr/bin/env python3
"""
🔗 PRIVY + HYPERLIQUID INTEGRATION
Following official Privy guide: https://docs.privy.io/recipes/hyperliquid-guide
"""

import os
import json
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from datetime import datetime

# Import Privy and Hyperliquid SDKs
try:
    from privy import PrivyAPI
    from hyperliquid.exchange import Exchange
    from hyperliquid.info import Info
    from hyperliquid.utils import constants
    SDK_AVAILABLE = True
except ImportError as e:
    SDK_AVAILABLE = False
    print(f"❌ Missing dependencies: {e}")
    print("Run: pip install privy hyperliquid-python-sdk>=0.14.1")

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class PrivyHyperliquidConfig:
    """Configuration for Privy + Hyperliquid integration"""
    privy_app_id: str
    privy_app_secret: str
    privy_authorization_key: str
    hyperliquid_base_url: str = "https://api.hyperliquid.xyz"
    is_testnet: bool = False
    
    @classmethod
    def from_env(cls):
        """Create config from environment variables"""
        # Try both naming conventions for Privy credentials
        privy_app_id = os.getenv('PRIVY_APP_ID') or os.getenv('PRIVYAPPID')
        privy_app_secret = os.getenv('PRIVY_APP_SECRET') or os.getenv('PRIVYAPPSECRET')
        
        return cls(
            privy_app_id=privy_app_id,
            privy_app_secret=privy_app_secret,
            privy_authorization_key=os.getenv('PRIVY_AUTHORIZATION_KEY'),
            hyperliquid_base_url=os.getenv('HYPERLIQUID_BASE_URL', 'https://api.hyperliquid.xyz'),
            is_testnet=os.getenv('HYPERLIQUID_TESTNET', 'false').lower() == 'true'
        )

class PrivyHyperliquidClient:
    """Privy + Hyperliquid integration following official guide"""
    
    def __init__(self, config: PrivyHyperliquidConfig):
        self.config = config
        self.privy_client = None
        self.exchange_clients = {}  # Cache for user exchange clients
        self.info_client = None
        
        if not SDK_AVAILABLE:
            raise ImportError("Required SDKs not available")
        
        self._initialize_privy()
        self._initialize_hyperliquid()
    
    def _initialize_privy(self):
        """Initialize Privy client following official guide"""
        try:
            # Set environment variables that Privy library might expect
            if self.config.privy_app_id:
                os.environ['PRIVYAPPID'] = self.config.privy_app_id
            if self.config.privy_app_secret:
                os.environ['PRIVYAPPSECRET'] = self.config.privy_app_secret
            
            self.privy_client = PrivyAPI(
                app_id=self.config.privy_app_id,
                app_secret=self.config.privy_app_secret
            )
            logger.info("✅ Privy client initialized")
        except Exception as e:
            logger.error(f"❌ Failed to initialize Privy client: {e}")
            raise
    
    def _initialize_hyperliquid(self):
        """Initialize Hyperliquid info client"""
        try:
            self.info_client = Info(self.config.hyperliquid_base_url)
            logger.info("✅ Hyperliquid info client initialized")
        except Exception as e:
            logger.error(f"❌ Failed to initialize Hyperliquid client: {e}")
            raise
    
    def create_user_exchange_client(self, wallet_id: str, wallet_address: str):
        """Create exchange client for a specific user following official guide"""
        try:
            # For now, create a basic exchange client without Privy signer
            # This will be updated when we have proper Privy integration
            from eth_account import Account
            account = Account.create()
            
            # Create Hyperliquid exchange client
            exchange = Exchange(
                account, 
                self.config.hyperliquid_base_url,
                account_address=wallet_address
            )
            
            # Cache the client
            self.exchange_clients[wallet_address] = exchange
            
            logger.info(f"✅ Created exchange client for {wallet_address}")
            return exchange
            
        except Exception as e:
            logger.error(f"❌ Failed to create exchange client: {e}")
            raise
    
    async def check_hyperliquid_account(self, wallet_address: str) -> bool:
        """Check if wallet has Hyperliquid account following official guide"""
        try:
            # Check if Hyperliquid account is active
            pre_transfer_check = self.info_client.pre_transfer_check({
                "user": wallet_address,
                "source": wallet_address,  # Use same address as source
            })
            
            if not pre_transfer_check.get('userExists', False):
                logger.warning(f"❌ Hyperliquid account does not exist for {wallet_address}")
                return False
            
            logger.info(f"✅ Hyperliquid account exists for {wallet_address}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error checking Hyperliquid account: {e}")
            return False
    
    async def get_tradable_assets(self) -> Dict[str, Any]:
        """Get available assets and contexts following official guide"""
        try:
            # Get available assets
            meta_and_ctx = self.info_client.meta_and_asset_ctxs()
            meta = meta_and_ctx[0]
            ctx = meta_and_ctx[1]
            
            logger.info(f"✅ Retrieved {len(meta['universe'])} tradable assets")
            return {
                'meta': meta,
                'ctx': ctx,
                'universe': meta['universe']
            }
            
        except Exception as e:
            logger.error(f"❌ Error getting tradable assets: {e}")
            raise
    
    async def place_order(self, wallet_address: str, asset: str, is_buy: bool, 
                         size: float, price: float = None, order_type: str = "market") -> Dict[str, Any]:
        """Place order following official guide"""
        try:
            # Get exchange client for user
            if wallet_address not in self.exchange_clients:
                raise ValueError(f"No exchange client found for {wallet_address}")
            
            exchange = self.exchange_clients[wallet_address]
            
            # Prepare order based on type
            if order_type == "market":
                order_params = {
                    "coin": asset,
                    "is_buy": is_buy,
                    "sz": size,
                    "limit_px": 0,  # Market order
                    "order_type": {"market": {}},
                    "reduce_only": False
                }
            else:  # Limit order
                order_params = {
                    "coin": asset,
                    "is_buy": is_buy,
                    "sz": size,
                    "limit_px": price,
                    "order_type": {"limit": {"tif": "Gtc"}},
                    "reduce_only": False
                }
            
            # Place order
            result = exchange.order(**order_params)
            
            logger.info(f"✅ Order placed: {result}")
            return result
            
        except Exception as e:
            logger.error(f"❌ Error placing order: {e}")
            raise
    
    async def get_user_state(self, wallet_address: str) -> Dict[str, Any]:
        """Get user state following official guide"""
        try:
            user_state = self.info_client.user_state(wallet_address)
            logger.info(f"✅ Retrieved user state for {wallet_address}")
            return user_state
            
        except Exception as e:
            logger.error(f"❌ Error getting user state: {e}")
            raise
    
    async def get_open_positions(self, wallet_address: str) -> List[Dict[str, Any]]:
        """Get open positions following official guide"""
        try:
            user_state = await self.get_user_state(wallet_address)
            positions = []
            
            for position in user_state.get('assetPositions', []):
                if float(position['position']['szi']) != 0:
                    positions.append({
                        'coin': position['position']['coin'],
                        'size': position['position']['szi'],
                        'entry_px': position['position'].get('entryPx'),
                        'unrealized_pnl': position['position'].get('unrealizedPnl', 0)
                    })
            
            logger.info(f"✅ Retrieved {len(positions)} open positions")
            return positions
            
        except Exception as e:
            logger.error(f"❌ Error getting open positions: {e}")
            raise

# Example usage following official guide
async def example_usage():
    """Example usage following official Privy guide"""
    try:
        # Initialize config
        config = PrivyHyperliquidConfig.from_env()
        
        # Create client
        client = PrivyHyperliquidClient(config)
        
        # Example wallet details (from your bot)
        wallet_id = "your-privy-wallet-id"
        wallet_address = "0x36d3099099225BBDE7A739E8858CD2B72130eb16"
        
        # Check if wallet has Hyperliquid account
        has_account = await client.check_hyperliquid_account(wallet_address)
        if not has_account:
            print("❌ Wallet needs to be activated on Hyperliquid first")
            return
        
        # Create exchange client
        exchange = client.create_user_exchange_client(wallet_id, wallet_address)
        
        # Get tradable assets
        assets = await client.get_tradable_assets()
        print(f"Available assets: {[asset['name'] for asset in assets['universe']]}")
        
        # Get user state
        user_state = await client.get_user_state(wallet_address)
        print(f"Account value: ${user_state.get('marginSummary', {}).get('accountValue', 0)}")
        
        # Place a market order (example)
        # result = await client.place_order(wallet_address, "BTC", True, 0.001)
        # print(f"Order result: {result}")
        
    except Exception as e:
        logger.error(f"❌ Example failed: {e}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(example_usage())
