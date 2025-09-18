#!/usr/bin/env python3
"""
🚀 Hyperliquid Bot + Supabase Integration
Enhanced trading bot with full Supabase integration for 100 users
"""

import os
import asyncio
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

# Import the original bot
from hyperliquid_auto_trading_bot import AutoTradingBot, UserState

# Import Supabase service
from supabase_trading_service import (
    get_trading_service, 
    UserData, 
    TradeData, 
    create_user, 
    get_user, 
    update_user, 
    create_trade
)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SupabaseUserState:
    """Enhanced UserState that syncs with Supabase"""
    
    def __init__(self, telegram_user_id: int, supabase_data: Dict[str, Any] = None):
        self.telegram_user_id = telegram_user_id
        self.supabase_service = get_trading_service()
        
        if supabase_data:
            self._load_from_supabase(supabase_data)
        else:
            self._initialize_defaults()
    
    def _load_from_supabase(self, data: Dict[str, Any]):
        """Load user state from Supabase data"""
        self.user_id = data.get('id')
        self.wallet_address = data.get('wallet_address')
        self.private_key = data.get('private_key_encrypted')
        self.mnemonic = data.get('mnemonic_encrypted')
        self.privy_user_id = data.get('privy_user_id')
        self.session_signer = data.get('session_signer')
        self.auto_trade_enabled = data.get('auto_trading_enabled', False)
        self.risk_per_trade = data.get('risk_per_trade', 0.05)
        self.max_position_size = data.get('max_position_size', 0.20)
        self.min_confidence = data.get('min_confidence', 70)
        self.total_trades = data.get('total_trades', 0)
        self.total_earnings = data.get('total_earnings', 0.0)
        self.win_rate = data.get('win_rate', 0.0)
        self.total_pnl = data.get('total_pnl', 0.0)
        self.is_active = data.get('is_active', True)
        self.last_active = data.get('last_active')
        
        # Initialize trade history (will be loaded separately)
        self.trades = []
    
    def _initialize_defaults(self):
        """Initialize with default values"""
        self.user_id = None
        self.wallet_address = None
        self.private_key = None
        self.mnemonic = None
        self.privy_user_id = None
        self.session_signer = None
        self.auto_trade_enabled = False
        self.risk_per_trade = 0.05
        self.max_position_size = 0.20
        self.min_confidence = 70
        self.total_trades = 0
        self.total_earnings = 0.0
        self.win_rate = 0.0
        self.total_pnl = 0.0
        self.is_active = True
        self.last_active = None
        self.trades = []
    
    async def save_to_supabase(self) -> bool:
        """Save current state to Supabase"""
        try:
            updates = {
                'wallet_address': self.wallet_address,
                'private_key_encrypted': self.private_key,
                'mnemonic_encrypted': self.mnemonic,
                'privy_user_id': self.privy_user_id,
                'session_signer': self.session_signer,
                'auto_trading_enabled': self.auto_trade_enabled,
                'risk_per_trade': self.risk_per_trade,
                'max_position_size': self.max_position_size,
                'min_confidence': self.min_confidence,
                'total_trades': self.total_trades,
                'total_earnings': self.total_earnings,
                'win_rate': self.win_rate,
                'total_pnl': self.total_pnl,
                'is_active': self.is_active,
                'last_active': datetime.now().isoformat()
            }
            
            # Remove None values
            updates = {k: v for k, v in updates.items() if v is not None}
            
            return await self.supabase_service.update_user(self.telegram_user_id, updates)
        except Exception as e:
            logger.error(f"Error saving user state to Supabase: {e}")
            return False
    
    async def load_trades_from_supabase(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Load user's trades from Supabase"""
        try:
            trades = await self.supabase_service.get_user_trades(self.telegram_user_id, limit)
            self.trades = trades
            return trades
        except Exception as e:
            logger.error(f"Error loading trades from Supabase: {e}")
            return []

class SupabaseTradingBot(AutoTradingBot):
    """Enhanced trading bot with Supabase integration"""
    
    def __init__(self):
        # Initialize the base bot
        super().__init__()
        
        # Initialize Supabase service
        self.supabase_service = get_trading_service()
        
        # Replace the users dict with Supabase-backed storage
        self.users = {}  # Cache for active users
        self.user_cache_ttl = 300  # 5 minutes cache TTL
        self.last_cache_update = {}
        
        logger.info("✅ Supabase Trading Bot initialized")
    
    async def get_user_state(self, telegram_user_id: int) -> SupabaseUserState:
        """Get user state from Supabase with caching"""
        try:
            # Check cache first
            if (telegram_user_id in self.users and 
                telegram_user_id in self.last_cache_update and
                datetime.now() - self.last_cache_update[telegram_user_id] < timedelta(seconds=self.user_cache_ttl)):
                return self.users[telegram_user_id]
            
            # Load from Supabase
            user_data = await self.supabase_service.get_user(telegram_user_id)
            
            if user_data:
                user_state = SupabaseUserState(telegram_user_id, user_data)
                self.users[telegram_user_id] = user_state
                self.last_cache_update[telegram_user_id] = datetime.now()
                return user_state
            else:
                # Create new user
                logger.info(f"Creating new user {telegram_user_id}")
                user_id = await create_user(telegram_user_id)
                if user_id:
                    user_state = SupabaseUserState(telegram_user_id)
                    user_state.user_id = user_id
                    self.users[telegram_user_id] = user_state
                    self.last_cache_update[telegram_user_id] = datetime.now()
                    return user_state
                else:
                    logger.error(f"Failed to create user {telegram_user_id}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error getting user state for {telegram_user_id}: {e}")
            return None
    
    async def save_user_state(self, user_state: SupabaseUserState) -> bool:
        """Save user state to Supabase"""
        try:
            success = await user_state.save_to_supabase()
            if success:
                # Update cache
                self.users[user_state.telegram_user_id] = user_state
                self.last_cache_update[user_state.telegram_user_id] = datetime.now()
            return success
        except Exception as e:
            logger.error(f"Error saving user state: {e}")
            return False
    
    # Override key methods to use Supabase
    
    async def start_command(self, update, context):
        """Enhanced start command with Supabase integration"""
        user_id = update.effective_user.id
        
        # Get or create user in Supabase
        user_state = await self.get_user_state(user_id)
        if not user_state:
            await update.message.reply_text("❌ Failed to initialize user. Please try again.")
            return
        
        # Update user info
        user_state.first_name = update.effective_user.first_name
        user_state.last_name = update.effective_user.last_name
        user_state.username = update.effective_user.username
        await self.save_user_state(user_state)
        
        # Show welcome message
        welcome_text = f"""
🚀 **Welcome to the Trading Bot!**

Hi {user_state.first_name or 'Trader'}! I'm your AI trading assistant.

**What I can do:**
• 🤖 **Auto-trading** - Trade automatically when I find strong signals
• 📊 **Market Analysis** - Get real-time market insights
• 💰 **Builder Fees** - Earn fees on every trade
• 🔒 **Secure Wallets** - Manage your crypto wallets safely

**Get Started:**
1. Create or import your wallet
2. Fund it with USDC
3. Enable auto-trading
4. Start earning!

Choose an option below to begin:
        """
        
        keyboard = [
            [{"text": "🆕 Create New Wallet", "callback_data": "create_wallet"}],
            [{"text": "📥 Import Wallet", "callback_data": "import_wallet"}],
            [{"text": "🔐 Social Login", "callback_data": "social_login"}],
            [{"text": "🤖 Enable Auto-Trading", "callback_data": "enable_auto"}],
            [{"text": "📊 View Signals", "callback_data": "view_signals"}],
            [{"text": "❓ Help", "callback_data": "show_help"}]
        ]
        
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            welcome_text,
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
    
    async def create_wallet_command(self, update, context):
        """Enhanced wallet creation with Supabase storage"""
        user_id = update.effective_user.id
        
        # Get user state
        user_state = await self.get_user_state(user_id)
        if not user_state:
            await update.message.reply_text("❌ Failed to get user state. Please try again.")
            return
        
        try:
            # Create wallet using Privy or basic method
            if self.privy_client:
                # Use Privy for wallet creation
                privy_user = await self._get_or_create_privy_user(str(user_id))
                
                if privy_user:
                    privy_user_id = privy_user.get('id')
                    wallet = self._create_wallet_for_user(privy_user_id)
                    
                    if wallet:
                        wallet_address = wallet.address
                        
                        # Update user state
                        user_state.privy_user_id = privy_user_id
                        user_state.wallet_address = wallet_address
                        user_state.session_signer = wallet.session_signer if hasattr(wallet, 'session_signer') else None
                        
                        # Save to Supabase
                        await self.save_user_state(user_state)
                        
                        await update.message.reply_text(
                            f"✅ **New Wallet Created with Privy!**\n\n"
                            f"**Your Wallet Address:** `{wallet_address}`\n\n"
                            f"**Security Features:**\n"
                            f"• Wallet managed securely by Privy\n"
                            f"• Session signer enabled for automated trading\n"
                            f"• No private keys stored in bot\n"
                            f"• Professional-grade security\n\n"
                            f"**Next Steps:**\n"
                            f"1. Fund your wallet with USDC\n"
                            f"2. Enable auto-trading\n"
                            f"3. Start earning builder fees!",
                            parse_mode='Markdown'
                        )
                        return
            
            # Fallback to basic wallet creation
            from eth_account import Account
            account = Account.create()
            wallet_address = account.address
            private_key = account.key.hex()
            
            # Update user state
            user_state.wallet_address = wallet_address
            user_state.private_key = private_key
            
            # Save to Supabase
            await self.save_user_state(user_state)
            
            await update.message.reply_text(
                f"✅ **New Wallet Created!**\n\n"
                f"**Your Wallet Address:** `{wallet_address}`\n\n"
                f"**Next Steps:**\n"
                f"1. Fund your wallet with USDC\n"
                f"2. Enable auto-trading\n"
                f"3. Start earning builder fees!",
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"Error creating wallet: {e}")
            await update.message.reply_text(
                f"❌ **Wallet Creation Failed**\n\n"
                f"Error: {str(e)}\n\n"
                f"Please try again or use `/import` to import an existing wallet.",
                parse_mode='Markdown'
            )
    
    async def balance_command(self, update, context):
        """Enhanced balance command with Supabase data"""
        user_id = update.effective_user.id
        
        # Get user state
        user_state = await self.get_user_state(user_id)
        if not user_state:
            await update.message.reply_text("Please use /start first!")
            return
        
        if not user_state.wallet_address:
            await update.message.reply_text(
                "❌ Please create or import your wallet first!"
            )
            return
        
        try:
            # Load recent trades from Supabase
            trades = await user_state.load_trades_from_supabase(limit=10)
            
            # Get performance data
            performance = await self.supabase_service.get_user_performance(user_id)
            
            balance_text = f"""
💰 <b>Account Balance</b>

<b>Wallet:</b> <code>{user_state.wallet_address}</code>
<b>Status:</b> ⚠️ New wallet - needs funding

This is your unique session wallet. To start trading:

1. **Fund your wallet** with USDC on Hyperliquid
2. **Enable auto-trading** using the button below
3. **Start earning** builder fees!

<b>Trading Stats:</b>
• Total Trades: {performance['total_trades']}
• Total Earnings: ${performance['total_earnings']:.4f}
• Win Rate: {performance['win_rate']:.1f}%
• Auto-Trading: {'✅ Enabled' if user_state.auto_trade_enabled else '❌ Disabled'}

<b>Recent Performance:</b>
• Best Trade: ${performance['best_trade']:.4f}
• Worst Trade: ${performance['worst_trade']:.4f}
• Avg Trade Size: ${performance['avg_trade_size']:.2f}
• Total Fees: ${performance['total_fees']:.4f}

<b>Next Steps:</b>
• Send USDC to your wallet address above
• Click "🤖 Enable Auto-Trading" to start
• The bot will automatically trade when funded"""
            
            await update.message.reply_text(
                balance_text,
                parse_mode='HTML'
            )
            
        except Exception as e:
            logger.error(f"Error getting balance: {e}")
            await update.message.reply_text(
                f"❌ **Balance Error**\n\n"
                f"Error: {str(e)}",
                parse_mode='Markdown'
            )
    
    async def _execute_trade(self, user_id: int, symbol: str, side: str, size: float) -> Dict[str, Any]:
        """Enhanced trade execution with Supabase logging"""
        try:
            # Execute the trade using the base bot
            trade_result = await super()._execute_trade(user_id, symbol, side, size)
            
            # Log trade to Supabase
            if trade_result.get('success'):
                trade_id = await create_trade(
                    telegram_user_id=user_id,
                    symbol=symbol,
                    side=side,
                    size=size,
                    price=trade_result.get('price', 0),
                    trade_type='AUTO' if self.users.get(user_id, {}).auto_trade_enabled else 'MANUAL'
                )
                
                if trade_id:
                    logger.info(f"✅ Trade logged to Supabase: {trade_id}")
                
                # Update trade with additional info
                if trade_id and 'order_id' in trade_result:
                    await self.supabase_service.update_trade(trade_id, {
                        'order_id': trade_result['order_id'],
                        'transaction_hash': trade_result.get('transaction_hash'),
                        'status': 'FILLED' if trade_result.get('success') else 'FAILED',
                        'executed_at': datetime.now().isoformat(),
                        'pnl': trade_result.get('pnl', 0),
                        'fees_paid': trade_result.get('fees_paid', 0),
                        'builder_fee_earned': trade_result.get('builder_fee_earned', 0)
                    })
            
            return trade_result
            
        except Exception as e:
            logger.error(f"Error executing trade: {e}")
            return {'success': False, 'error': str(e)}
    
    async def get_bot_stats(self) -> Dict[str, Any]:
        """Get comprehensive bot statistics"""
        try:
            active_users = await self.supabase_service.get_active_users()
            analytics = await self.supabase_service.get_bot_analytics()
            
            return {
                'total_users': len(active_users),
                'active_users': len([u for u in active_users if u.get('last_active')]),
                'auto_trading_users': len([u for u in active_users if u.get('auto_trading_enabled')]),
                'total_trades': sum(u.get('total_trades', 0) for u in active_users),
                'total_earnings': sum(u.get('total_earnings', 0) for u in active_users),
                'analytics': analytics
            }
        except Exception as e:
            logger.error(f"Error getting bot stats: {e}")
            return {}

# Main execution
if __name__ == "__main__":
    print("🚀 Starting Supabase-Enhanced Trading Bot...")
    
    # Check Supabase configuration
    if not os.getenv('SUPABASE_URL') or not os.getenv('SUPABASE_ANON_KEY'):
        print("❌ Supabase not configured!")
        print("Set SUPABASE_URL and SUPABASE_ANON_KEY environment variables")
        exit(1)
    
    # Start the bot
    bot = SupabaseTradingBot()
    bot.run()

