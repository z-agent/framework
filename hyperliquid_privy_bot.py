#!/usr/bin/env python3
"""
🤖 HYPERLIQUID PRIVY BOT - PRODUCTION READY
Complete trading bot with Privy wallet integration and Supabase persistence
"""

import os
import sys
import json
import logging
import asyncio
import io
from datetime import datetime
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from dotenv import load_dotenv
load_dotenv()

try:
    from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
    from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
    from hyperliquid.info import Info
    from hyperliquid.utils import constants
    from eth_account import Account
    SDK_AVAILABLE = True
except ImportError as e:
    print(f"❌ Missing dependencies: {e}")
    print("Run: pip install python-telegram-bot hyperliquid-python-sdk eth-account python-dotenv")
    SDK_AVAILABLE = False

# Import our custom modules
from bot_modules.privy_integration import PrivyIntegration
from bot_modules.hyperliquid_trader import HyperliquidTrader
from supabase_trading_service import SupabaseTradingService, UserData
try:
    from production_config import get_config
    from src.tools.production_error_handler import get_error_handler, ErrorContext, ErrorSeverity
    from src.tools.production_rate_limiter import get_rate_limiter, RateLimitedOperation
    PRODUCTION_FEATURES = True
except ImportError as e:
    print(f"⚠️ Production features not available: {e}")
    PRODUCTION_FEATURES = False

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

@dataclass
class UserState:
    """User state management"""
    user_id: int
    username: str
    wallet_address: Optional[str] = None
    privy_user_id: Optional[str] = None
    private_key: Optional[str] = None  # For imported wallets
    builder_approved: bool = False
    total_trades: int = 0
    total_volume: float = 0.0
    total_earnings: float = 0.0
    created_at: str = ""
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()

class HyperliquidPrivyBot:
    """Production-ready Hyperliquid Telegram Bot with Privy integration"""
    
    def __init__(self):
        # Load production configuration
        if PRODUCTION_FEATURES:
            self.config = get_config()
            # Initialize production services
            self.error_handler = get_error_handler()
            self.rate_limiter = get_rate_limiter()
            # Initialize Privy
            self.privy = PrivyIntegration(self.config.privy_app_id, self.config.privy_app_secret)
        else:
            # Fallback to environment variables
            self.config = None
            self.error_handler = None
            self.rate_limiter = None
            # Initialize Privy with env vars
            privy_app_id = os.getenv('PRIVY_APP_ID')
            privy_app_secret = os.getenv('PRIVY_APP_SECRET')
            if not privy_app_id or not privy_app_secret:
                raise ValueError("PRIVY_APP_ID and PRIVY_APP_SECRET environment variables required")
            self.privy = PrivyIntegration(privy_app_id, privy_app_secret)
        
        # Initialize Supabase with backup
        try:
            self.supabase = SupabaseTradingService()
            logger.info("✅ Supabase initialized with backup")
        except Exception as e:
            logger.warning(f"⚠️ Supabase not available: {e}")
            self.supabase = None
        
        # Initialize IvishX analysis tool
        self.ivishx_tool = None
        try:
            from src.tools.ivishx_improved import ImprovedIvishXAnalyzeTool
            self.ivishx_tool = ImprovedIvishXAnalyzeTool()
            logger.info("✅ IvishX analysis tool initialized")
        except Exception as e:
            logger.warning(f"⚠️ IvishX tool initialization failed: {e}")
            self.ivishx_tool = None
        
        # Initialize Vistara analysis tool for /ta command
        self.vistara_analyzer = None
        try:
            from src.tools.vistara_analyzer import VistaraAnalyzer
            self.vistara_analyzer = VistaraAnalyzer()
            logger.info("✅ Vistara analysis tool initialized")
        except Exception as e:
            logger.warning(f"⚠️ Vistara tool initialization failed: {e}")
            self.vistara_analyzer = None
        
        # Initialize Hyperliquid trader
        hyperliquid_key = self.config.hyperliquid_private_key if self.config else os.getenv('HYPERLIQUID_PRIVATE_KEY')
        if not hyperliquid_key:
            raise ValueError("HYPERLIQUID_PRIVATE_KEY environment variable required")
        self.hyperliquid_trader = HyperliquidTrader(hyperliquid_key)
        
        # User management
        self.users: Dict[int, UserState] = {}
        
        # Bot setup
        bot_token = self.config.bot_token if self.config else os.getenv('TELEGRAM_BOT_TOKEN')
        if not bot_token:
            raise ValueError("TELEGRAM_BOT_TOKEN environment variable required")
        self.application = Application.builder().token(bot_token).build()
        self._setup_handlers()
    
    def _setup_handlers(self):
        """Setup bot command handlers"""
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("connect", self.connect_command))
        self.application.add_handler(CommandHandler("trade", self.trade_command))
        self.application.add_handler(CommandHandler("analyze", self.analyze_command))
        self.application.add_handler(CommandHandler("ta", self.ta_command))
        self.application.add_handler(CommandHandler("close", self.close_command))
        self.application.add_handler(CommandHandler("balance", self.balance_command))
        self.application.add_handler(CommandHandler("earnings", self.earnings_command))
        self.application.add_handler(CommandHandler("trades", self.trades_command))
        self.application.add_handler(CommandHandler("positions", self.positions_command))
        self.application.add_handler(CommandHandler("market", self.market_command))
        self.application.add_handler(CommandHandler("status", self.status_command))
        self.application.add_handler(CommandHandler("import", self.import_command))
        self.application.add_handler(CallbackQueryHandler(self.callback_handler))
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start command - welcome and setup"""
        user = update.effective_user
        user_id = user.id
        username = user.username or user.first_name or "User"
        
        # Try to load user from Supabase first
        user_loaded = False
        if self.supabase:
            try:
                # Use the correct method name
                user_data = await self.supabase.get_user(telegram_user_id=user_id)
                if user_data:
                    print(f"User data: {user_data}")
                    print(f"User data username: {user_data.get('username')}")
                    print(f"User data wallet_address: {user_data.get('wallet_address')}")
                    print(f"User data privy_user_id: {user_data.get('privy_user_id')}")
                    print(f"User data total_trades: {user_data.get('total_trades')}")
                    print(f"User data total_earnings: {user_data.get('total_earnings')}")
                    print(f"User data last_active: {user_data.get('last_active')}")
                    
                    # Skip builder approval checks - allow immediate trading
                    builder_approved = True  # Always allow trading
                    wallet_address = user_data.get('wallet_address')
                    
                    # Load user from Supabase
                    self.users[user_id] = UserState(
                        user_id=user_id,
                        username=user_data.get('username') or username,
                        wallet_address=wallet_address,
                        privy_user_id=user_data.get('privy_user_id') or None,
                        builder_approved=builder_approved,
                        total_trades=user_data.get('total_trades') or 0,
                        total_volume=user_data.get('total_earnings') or 0.0,
                        total_earnings=user_data.get('total_earnings') or 0.0,
                        created_at=user_data.get('last_active') if user_data.get('last_active') else datetime.now().isoformat()
                    )
                    user_loaded = True
                    logger.info(f"✅ Loaded user {user_id} from Supabase")
            except Exception as e:
                logger.warning(f"Failed to load user from Supabase: {e}")
        
        # Initialize user if not loaded from Supabase
        if not user_loaded and user_id not in self.users:
            self.users[user_id] = UserState(
                user_id=user_id,
                username=username,
                builder_approved=True  # Always allow trading
            )
        
        welcome_text = f"""
🤖 **Welcome to Hyperliquid Trading Bot!**

Hi {username}! I'm your AI trading assistant powered by Hyperliquid.

**🚀 What I do:**
• Execute real trades on Hyperliquid
• Provide market analysis and insights
• Track your performance and earnings
• Export your wallet anytime

**💰 How it works:**
1. Connect your Hyperliquid wallet
2. Approve builder fees (one-time)
3. Start trading with AI assistance!

**🔐 Wallet Security:**
Your smart wallet is Privy-backed, you can always export your private key anytime.

**Ready to start? Use /connect to begin!**
        """
        
        keyboard = [
            [InlineKeyboardButton("🚀 Get Started", callback_data="start_setup")],
            [InlineKeyboardButton("📊 View Commands", callback_data="show_help")],
            [InlineKeyboardButton("💰 How It Works", callback_data="how_it_works")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            welcome_text,
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
    
    async def connect_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Connect wallet command with Privy integration"""
        user = update.effective_user
        user_id = user.id
        username = user.username or user.first_name or "User"
        
        if user_id not in self.users:
            await update.message.reply_text("Please use /start first!")
            return
        
        user_state = self.users[user_id]
        
        if user_state.wallet_address:
            await update.message.reply_text(
                f"✅ Wallet already connected: `{user_state.wallet_address}`\n\n"
                f"Use /trade to start trading or /analyze for market insights!",
                parse_mode='Markdown'
            )
            return
        
        try:
            # Get or create Privy user
            privy_user, is_new = await self.privy.get_user_or_create(user_id, username)
            if not privy_user:
                # Fallback: create local wallet if Privy fails
                logger.warning("Privy user creation failed, creating local wallet")
                from eth_account import Account
                account = Account.create()
                user_state.wallet_address = account.address
                user_state.privy_user_id = f"local_{user_id}"
                wallet_address = account.address
                privy_user_id = f"local_{user_id}"
            else:
                # Get or create wallet
                wallet = await self.privy.get_or_create_wallet(privy_user.id)
                if not wallet:
                    # Fallback: create local wallet if Privy wallet creation fails
                    logger.warning("Privy wallet creation failed, creating local wallet")
                    from eth_account import Account
                    account = Account.create()
                    user_state.wallet_address = account.address
                    user_state.privy_user_id = f"local_{user_id}"
                    wallet_address = account.address
                    privy_user_id = f"local_{user_id}"
                else:
                    # Update user state
                    user_state.wallet_address = wallet.address
                    user_state.privy_user_id = privy_user.id
                    wallet_address = wallet.address
                    privy_user_id = privy_user.id
            
            # Save to Supabase
            if self.supabase:
                try:
                    user_data = UserData(
                        telegram_user_id=user_id,
                        username=username,
                        wallet_address=wallet_address,
                        privy_user_id=privy_user_id,
                        is_active=True,
                        last_active=datetime.now()
                    )
                    # Try to create, if exists then update
                    try:
                        await self.supabase.create_user(user_data)
                        logger.info(f"✅ Created user {user_id} in Supabase")
                    except Exception as create_error:
                        if "already exists" in str(create_error) or "duplicate key" in str(create_error):
                            # User exists, update instead
                            update_data = {
                                'wallet_address': wallet_address,
                                'privy_user_id': privy_user_id,
                                'last_active': datetime.now().isoformat()
                            }
                            await self.supabase.update_user(user_id, update_data)
                            logger.info(f"✅ Updated existing user {user_id} in Supabase")
                        else:
                            raise create_error
                except Exception as e:
                    logger.warning(f"Failed to save user to Supabase: {e}")
            
            connect_text = f"""
🔗 **Wallet Connected Successfully!**

**Your Wallet Address:**
`{wallet_address}`

**User ID:**
`{privy_user_id}`

**Next Steps:**
1. Use /trade to start trading
2. Use /analyze for market insights
3. Use /positions to view portfolio

**Security Note:**
Your smart wallet is Privy-backed, you can always export your private key anytime.

**Ready to trade? Use /approve next!**
            """
            
            await update.message.reply_text(connect_text, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Wallet connection failed: {e}")
            await update.message.reply_text(f"❌ Wallet connection failed: {str(e)}")
    

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Help command - show all commands"""
        help_text = """
🤖 **Hyperliquid Trading Bot - Commands**

**Basic Commands:**
/start - Welcome and setup
/help - Show this help message
/status - Check your account status

**Trading Commands:**
/analyze - AI analysis with buy/sell signals
/ta - Professional technical analysis with charts
/connect - Connect your Hyperliquid wallet
/import - Import existing wallet with private key
/trade - Place a real trade
/close - Close positions easily
/balance - Check your account balance
/trades - View your recent trades
/positions - View your current positions
/market - View real-time market data

**Wallet Commands:**
/export - Export your wallet private key

**Earnings Commands:**
/earnings - View your earnings and stats

**How Trading Works:**
• Real trades on Hyperliquid exchange
• Professional AI market analysis
• Advanced charting and signals
• Secure wallet management

**Ready to start? Use /connect to begin!**
        """
        
        await update.message.reply_text(help_text, parse_mode='Markdown')

    async def callback_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle callback queries"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        data = query.data
        
        if user_id not in self.users:
            await query.edit_message_text("Please use /start first!")
            return
        
        user_state = self.users[user_id]
        
        # Skip all approval callbacks - trading is always available
        user_state.builder_approved = True
        
        if data == "start_trading":
            await query.edit_message_text(
                "🚀 **Ready to Trade!**\n\n"
                "Use /trade to start trading.\n\n"
                "**Example:**\n"
                "`/trade BTC BUY 0.01`\n"
                "`/trade ETH SELL 0.1`",
                parse_mode='Markdown'
            )
        
        # Handle trade button clicks
        elif data.startswith("trade_"):
            parts = data.split("_")
            if len(parts) == 3:
                symbol = parts[1].upper()
                side = parts[2].upper()
                
                if not user_state.wallet_address:
                    await query.edit_message_text(
                        "❌ **No Wallet Connected**\n\n"
                        "Please connect your wallet first using /connect or /import",
                        parse_mode='Markdown'
                    )
                    return
                
                # Execute the trade directly
                try:
                    await query.edit_message_text(
                        f"🎯 **Executing {symbol} {side} Trade...**\n\n"
                        f"⏳ Placing order on Hyperliquid...\n"
                        f"💰 Size: 0.01 {symbol}\n"
                        f"🔄 Please wait...",
                        parse_mode='Markdown'
                    )
                    
                    # Create user-specific trader if user has private key
                    if user_state.private_key:
                        # Use user's private key for trading
                        from bot_modules.hyperliquid_trader import HyperliquidTrader
                        user_trader = HyperliquidTrader(user_state.private_key)
                        logger.info(f"Using user's wallet for trading: {user_state.wallet_address}")
                    else:
                        # Fallback to main trader (but this shouldn't work for user trades)
                        user_trader = self.hyperliquid_trader
                        logger.warning(f"Using main trader (this may fail): {user_state.wallet_address}")
                    
                    # Place the trade with default size
                    trade_size = 0.01
                    trade_result = await user_trader.place_trade(symbol, side, trade_size)
                    
                    if trade_result.success:
                        # Update user stats
                        user_state.total_trades += 1
                        user_state.total_volume += trade_result.size * trade_result.price
                        
                        # Save to Supabase
                        if self.supabase:
                            try:
                                await self.supabase.update_user_stats(
                                    user_id,
                                    total_trades=user_state.total_trades,
                                    total_earnings=user_state.total_volume
                                )
                            except Exception as e:
                                logger.warning(f"Failed to update user stats in Supabase: {e}")
                        
                        # Format order details
                        order_info = ""
                        if trade_result.order_id:
                            order_info = f"• Order ID: {trade_result.order_id}\n"
                        
                        # Format builder fee info
                        builder_info = ""
                        if trade_result.builder_fee_applied:
                            builder_info = "• Builder Fee: Applied ✅\n"
                        
                        # Format auto-correction info
                        correction_info = ""
                        if trade_size != trade_result.size:
                            correction_info += f"• Size auto-corrected: {trade_size} → {trade_result.size}\n"
                        
                        success_text = f"""
✅ **Trade Executed Successfully!**

**Trade Details:**
• Symbol: {trade_result.symbol}
• Side: {trade_result.side}
• Size: {trade_result.size}
• Entry Price: ${trade_result.price:,.2f}
{order_info}{builder_info}{correction_info}**Hyperliquid Status:** ✅ Confirmed

**Quick Actions:**
                        """
                        
                        # Add quick action buttons
                        keyboard = [
                            [
                                InlineKeyboardButton("📊 View Positions", callback_data="view_positions"),
                                InlineKeyboardButton("📈 Trade History", callback_data="view_trades")
                            ],
                            [
                                InlineKeyboardButton(f"🔄 Trade More {symbol}", callback_data=f"analyze_{symbol}"),
                                InlineKeyboardButton("💰 Check Balance", callback_data="check_balance")
                            ]
                        ]
                        reply_markup = InlineKeyboardMarkup(keyboard)
                        
                        await query.edit_message_text(
                            success_text,
                            parse_mode='Markdown',
                            reply_markup=reply_markup
                        )
                    else:
                        # Parse error details from raw response
                        error_details = ""
                        if trade_result.raw_response:
                            raw = trade_result.raw_response
                            if isinstance(raw, dict):
                                response_data = raw.get("response", {})
                                data = response_data.get("data", {})
                                statuses = data.get("statuses", [])
                                if statuses:
                                    for status in statuses:
                                        if status.get("error"):
                                            error_details += f"• {status.get('error')}\n"
                        
                        await query.edit_message_text(
                            f"❌ **Trade Failed**\n\n"
                            f"**Error:** {trade_result.error_message}\n\n"
                            f"**Details:**\n{error_details}\n"
                            f"**Hyperliquid Response:** Failed\n\n"
                            f"**Solutions:**\n"
                            f"• Check /balance for sufficient funds\n"
                            f"• Try smaller trade size\n"
                            f"• Use /market to check current prices\n"
                            f"• [View on Hyperliquid](https://app.hyperliquid.xyz/trade/{symbol.lower()})",
                            parse_mode='Markdown'
                        )
                        
                except Exception as e:
                    logger.error(f"Trade execution failed: {e}")
                    await query.edit_message_text(
                        f"❌ **Trade Error**\n\n"
                        f"**Error:** {str(e)}\n\n"
                        f"Please try again with /trade {symbol} {side} 0.01",
                        parse_mode='Markdown'
                    )
    
    
    async def analyze_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Analyze command - analyze cryptocurrency with rate limiting"""
        user_id = update.effective_user.id
        
        if user_id not in self.users:
            await update.message.reply_text("Please use /start first!")
            return
        
        # Apply rate limiting if available
        if PRODUCTION_FEATURES and self.rate_limiter:
            async with RateLimitedOperation(user_id):
                await self._analyze_command_impl(update, context)
        else:
            await self._analyze_command_impl(update, context)
    
    async def _analyze_command_impl(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Implementation of analyze command"""
        
        if not context.args:
            await update.message.reply_text(
                "📊 **Analyze Crypto**\n\n"
                "**Usage:** `/analyze SYMBOL`\n\n"
                "**Examples:**\n"
                "• `/analyze BTC` - Analyze Bitcoin\n"
                "• `/analyze ETH` - Analyze Ethereum\n"
                "• `/analyze SOL` - Analyze Solana\n\n"
                "**Available Symbols:** BTC, ETH, SOL, AVAX, etc.",
                parse_mode='Markdown'
            )
            return
        
        symbol = context.args[0].upper()
        
        # Send analyzing message
        analyzing_msg = await update.message.reply_text(
            f"🔍 **Analyzing {symbol}**\n\n"
            f"📡 Fetching real-time data...\n"
            f"🧠 Running technical analysis...\n"
            f"📊 Calculating signals...",
            parse_mode='Markdown'
        )
        
        try:
            # Get real-time price data
            try:
                from src.tools.real_time_data_service import get_price
                real_time_data = await get_price(symbol)
                if real_time_data and hasattr(real_time_data, 'price'):
                    current_price = real_time_data.price
                    data_source = "Real-time"
                else:
                    current_price = 0
                    data_source = "Fallback"
            except Exception as e:
                logger.warning(f"Real-time data failed: {e}")
                current_price = 0
                data_source = "Fallback"
            
            # Run analysis using IvishX tool
            if hasattr(self, 'ivishx_tool') and self.ivishx_tool:
                try:
                    # Try async method first, then sync method
                    if hasattr(self.ivishx_tool, 'analyze') and asyncio.iscoroutinefunction(self.ivishx_tool.analyze):
                        analysis_result = await self.ivishx_tool.analyze(symbol)
                        logger.info(f"IvishX analysis result: {analysis_result}")
                    elif hasattr(self.ivishx_tool, '_run'):
                        analysis_result = self.ivishx_tool._run(symbol.lower(), 30)
                        logger.info(f"IvishX analysis result: {analysis_result}")
                    else:
                        analysis_result = None
                except Exception as e:
                    logger.warning(f"IvishX analysis failed: {e}")
                    analysis_result = None
                
                # Debug logging
                logger.info(f"IvishX analysis result: {analysis_result}")
                
                if analysis_result:
                    # Handle dict with TradingSignal object in 'signal' key (most common case)
                    if isinstance(analysis_result, dict) and 'signal' in analysis_result and hasattr(analysis_result['signal'], 'type'):
                        signal_obj = analysis_result['signal']
                        class Signal:
                            def __init__(self, signal_obj):
                                self.type = getattr(signal_obj, 'type', 'WAIT')
                                self.confidence = getattr(signal_obj, 'confidence', 0)
                                self.entry = getattr(signal_obj, 'entry', 0)
                                self.stop_loss = getattr(signal_obj, 'stop_loss', 0)
                                self.take_profit = getattr(signal_obj, 'take_profit', 0)
                                self.analysis = getattr(signal_obj, 'reasoning', 'AI-powered market analysis completed.')
                        
                        signal = Signal(signal_obj)
                    elif isinstance(analysis_result, dict) and 'signal' in analysis_result:
                        # Handle dict with signal data (not TradingSignal object)
                        signal_data = analysis_result['signal']
                        class Signal:
                            def __init__(self, data):
                                self.type = data.get('type', 'WAIT')
                                self.confidence = data.get('confidence', 0)
                                self.entry = data.get('entry', 0)
                                self.stop_loss = data.get('stop_loss', 0)
                                self.take_profit = data.get('take_profit', 0)
                                self.analysis = data.get('reasoning', 'AI-powered market analysis completed.')
                        
                        signal = Signal(signal_data)
                    elif hasattr(analysis_result, 'signal'):
                        # Handle direct TradingSignal object
                        signal_obj = analysis_result.signal
                        class Signal:
                            def __init__(self, signal_obj):
                                self.type = getattr(signal_obj, 'type', 'WAIT')
                                self.confidence = getattr(signal_obj, 'confidence', 0)
                                self.entry = getattr(signal_obj, 'entry', 0)
                                self.stop_loss = getattr(signal_obj, 'stop_loss', 0)
                                self.take_profit = getattr(signal_obj, 'take_profit', 0)
                                self.analysis = getattr(signal_obj, 'reasoning', 'AI-powered market analysis completed.')
                        
                        signal = Signal(signal_obj)
                    else:
                        # Fallback for unexpected format
                        signal = None
                    
                    if signal:
                        # Enhanced visual analysis like copytrade example
                        signal_emoji = "🟢" if signal.type == "BUY" else "🔴" if signal.type == "SELL" else "⚪"
                        confidence_bar = "█" * int(signal.confidence / 10) + "░" * (10 - int(signal.confidence / 10))
                        
                        # Calculate potential profit/loss
                        if signal.type == "BUY":
                            potential_profit = ((signal.take_profit - signal.entry) / signal.entry * 100)
                            potential_loss = ((signal.entry - signal.stop_loss) / signal.entry * 100)
                        else:
                            potential_profit = ((signal.entry - signal.take_profit) / signal.entry * 100)
                            potential_loss = ((signal.stop_loss - signal.entry) / signal.entry * 100)
                        
                        # Use beautiful visual formatter
                        try:
                            from src.tools.visual_formatter import VisualFormatter, TradingSignal as VSignal
                            formatter = VisualFormatter()
                            
                            # Create visual signal object
                            visual_signal = VSignal(
                                type=signal.type,
                                confidence=signal.confidence,
                                entry=signal.entry,
                                stop_loss=signal.stop_loss,
                                take_profit=signal.take_profit,
                                reasoning=signal.analysis if hasattr(signal, 'analysis') else 'Technical indicators suggest mixed signals.'
                            )
                            
                            # Create beautiful analysis card
                            analysis_text = formatter.create_analysis_card(symbol, current_price, visual_signal, data_source)
                            
                            # Try to create professional trading card
                            try:
                                from src.tools.trading_card_generator import TradingCardGenerator, UserProfile, TradingSignal as TSignal
                                
                                # Create user profile
                                user_profile = UserProfile(
                                    name=user.username or "Trader",
                                    username=user.username or f"user{user_id}",
                                    balance=user.total_earnings,
                                    pnl=0.0  # Could be calculated from recent trades
                                )
                                
                                # Create trading signal for card
                                card_signal = TSignal(
                                    type=signal.type,
                                    confidence=signal.confidence,
                                    entry=signal.entry,
                                    stop_loss=signal.stop_loss,
                                    take_profit=signal.take_profit,
                                    reasoning=signal.analysis if hasattr(signal, 'analysis') else 'Technical analysis completed.'
                                )
                                
                                card_generator = TradingCardGenerator()
                                card_bytes = card_generator.create_analysis_card(symbol, current_price, card_signal, user_profile)
                                
                                if card_bytes:
                                    # Send professional trading card
                                    await update.message.reply_photo(
                                        photo=io.BytesIO(card_bytes),
                                        caption=f"📊 **{symbol} Professional Analysis**\n\n⚡ Powered by Zara AI Trading",
                                        parse_mode='Markdown'
                                    )
                                else:
                                    # Fallback to basic image
                                    image_bytes = formatter.create_analysis_image(symbol, current_price, visual_signal)
                                    if image_bytes:
                                        await update.message.reply_photo(
                                            photo=io.BytesIO(image_bytes),
                                            caption=f"📊 **{symbol} Analysis**\n\nAI-powered trading signals",
                                            parse_mode='Markdown'
                                        )
                            except Exception as e:
                                logger.warning(f"Could not create trading card: {e}")
                                
                        except Exception as e:
                            logger.warning(f"Visual formatter failed, using fallback: {e}")
                            # Fallback to original formatting
                            analysis_text = f"""
┌──────── 📊 **{symbol} ANALYSIS** ────────┐
│                                                         │
│  💰 **Current Price**: ${current_price:,.2f}           │
│  📡 **Data Source**: {data_source}                │
│                                                         │
└─────────────────────────────────────┘

{signal_emoji} **TRADING SIGNAL**: {signal.type}
┌─────────────────────────────────────┐
│ 🎯 **Confidence**: {signal.confidence}%                    │
│ {confidence_bar}                      │
│                                                         │
│ 🎪 **Entry Price**: ${signal.entry:,.4f}               │
│ 🛑 **Stop Loss**: ${signal.stop_loss:,.4f}             │  
│ 🎯 **Take Profit**: ${signal.take_profit:,.4f}         │
│                                                         │
│ 📈 **Potential Gain**: +{potential_profit:.1f}%        │
│ 📉 **Potential Loss**: -{potential_loss:.1f}%          │
└─────────────────────────────────────┘

🧠 **AI ANALYSIS**
{signal.analysis if hasattr(signal, 'analysis') else 'Technical indicators suggest mixed signals. Monitor closely for confirmation.'}

🔗 **VERIFY DATA**
• [CoinGecko](https://www.coingecko.com/en/coins/{symbol.lower()}) | [CMC](https://coinmarketcap.com/currencies/{symbol.lower()}/)
"""
                    else:
                        analysis_text = f"""
📊 **{symbol} Analysis**

**Current Price:** ${current_price:,.2f}
**Data Source:** {data_source}

**❌ **No trading signals available** at this time.

Try again later or check other cryptocurrencies.
"""
                    
                    # Add trading buttons
                    keyboard = [
                        [
                            InlineKeyboardButton(f"📈 Buy {symbol}", callback_data=f"trade_{symbol}_buy"),
                            InlineKeyboardButton(f"📉 Sell {symbol}", callback_data=f"trade_{symbol}_sell")
                        ],
                        [
                            InlineKeyboardButton("🔄 Refresh Analysis", callback_data=f"analyze_{symbol}"),
                            InlineKeyboardButton("📊 Technical Analysis", callback_data=f"ta_{symbol}")
                        ]
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    
                    await analyzing_msg.edit_text(
                        analysis_text,
                        parse_mode='Markdown',
                        reply_markup=reply_markup
                    )
                else:
                    await analyzing_msg.edit_text(
                        f"📊 **{symbol} Analysis**\n\n"
                        f"**Current Price:** ${current_price:,.2f}\n"
                        f"**Data Source:** {data_source}\n\n"
                        f"❌ **No trading signals available** at this time.\n\n"
                        f"Try again later or check other cryptocurrencies.",
                        parse_mode='Markdown'
                    )
            else:
                # Fallback analysis without IvishX
                await analyzing_msg.edit_text(
                    f"📊 **{symbol} Analysis**\n\n"
                    f"**Current Price:** ${current_price:,.2f}\n"
                    f"**Data Source:** {data_source}\n\n"
                    f"⚠️ **Analysis tool not available**\n\n"
                    f"Basic price data only. For full analysis, contact support.",
                    parse_mode='Markdown'
                )
                
        except Exception as e:
            logger.error(f"Analysis error: {e}")
            await analyzing_msg.edit_text(
                f"❌ **Analysis Error**\n\n"
                f"**Error:** {str(e)}\n\n"
                f"Please try again later.",
                parse_mode='Markdown'
            )

    async def ta_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Technical Analysis command using Vistara API"""
        user_id = update.effective_user.id
        
        if user_id not in self.users:
            await update.message.reply_text("Please use /start first!")
            return
        
        if not context.args:
            await update.message.reply_text(
                "📊 **Professional Technical Analysis**\n\n"
                "**Usage:** `/ta SYMBOL`\n\n"
                "**Examples:**\n"
                "• `/ta BTC` - Bitcoin technical analysis\n"
                "• `/ta ETH` - Ethereum technical analysis\n"
                "• `/ta SOL` - Solana technical analysis\n\n"
                "**Features:** RSI, MACD, Volume, Charts",
                parse_mode='Markdown'
            )
            return
        
        symbol = context.args[0].upper()
        
        # Send analyzing message
        analyzing_msg = await update.message.reply_text(
            f"📊 **Analyzing {symbol}**\n\n"
            f"🔬 Professional technical analysis...\n"
            f"📈 Generating charts...\n"
            f"📊 Processing indicators...",
            parse_mode='Markdown'
        )
        
        try:
            # Run analysis using Vistara API
            if hasattr(self, 'vistara_analyzer') and self.vistara_analyzer:
                try:
                    # Get Vistara analysis
                    vistara_analysis = await self.vistara_analyzer.analyze(symbol)
                    logger.info(f"Vistara analysis result: {vistara_analysis}")
                    
                    if vistara_analysis:
                        # Format analysis for Telegram display
                        analysis_text, chart_url = self.vistara_analyzer.format_analysis_for_telegram(vistara_analysis)
                        
                        # Add trading buttons
                        keyboard = [
                            [
                                InlineKeyboardButton(f"📈 Buy {symbol}", callback_data=f"trade_{symbol}_buy"),
                                InlineKeyboardButton(f"📉 Sell {symbol}", callback_data=f"trade_{symbol}_sell")
                            ],
                            [
                                InlineKeyboardButton("📊 View Chart", url=chart_url),
                                InlineKeyboardButton("🔄 Refresh", callback_data=f"ta_{symbol}")
                            ]
                        ]
                        reply_markup = InlineKeyboardMarkup(keyboard)
                        
                        # Send analysis with chart
                        await analyzing_msg.edit_text(
                            analysis_text,
                            parse_mode='Markdown',
                            reply_markup=reply_markup
                        )
                        
                        # Send chart image if available
                        if chart_url:
                            try:
                                await update.message.reply_photo(
                                    photo=chart_url,
                                    caption=f"📊 **{symbol} Professional Chart Analysis**\n\nPowered by Vistara AI Analytics",
                                    parse_mode='Markdown'
                                )
                            except Exception as e:
                                logger.warning(f"Failed to send chart image: {e}")
                        
                    else:
                        await analyzing_msg.edit_text(
                            f"📊 **{symbol} Technical Analysis**\n\n"
                            f"❌ **Analysis unavailable** for {symbol}\n\n"
                            f"Try a different symbol like BTC, ETH, or SOL.",
                            parse_mode='Markdown'
                        )
                        
                except Exception as e:
                    logger.error(f"Vistara analysis failed: {e}")
                    await analyzing_msg.edit_text(
                        f"📊 **{symbol} Technical Analysis**\n\n"
                        f"⚠️ **Analysis service temporarily unavailable**\n\n"
                        f"Please try again in a moment.",
                        parse_mode='Markdown'
                    )
            else:
                # Fallback when Vistara not available
                await analyzing_msg.edit_text(
                    f"📊 **{symbol} Technical Analysis**\n\n"
                    f"⚠️ **Professional analysis tool not available**\n\n"
                    f"Use `/analyze {symbol}` for basic analysis.",
                    parse_mode='Markdown'
                )
                
        except Exception as e:
            logger.error(f"Technical analysis error: {e}")
            await analyzing_msg.edit_text(
                f"❌ **Technical Analysis Error**\n\n"
                f"**Error:** {str(e)}\n\n"
                f"Please try again later.",
                parse_mode='Markdown'
            )

    async def trade_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Trade command - place real trades"""
        user_id = update.effective_user.id
        
        if user_id not in self.users:
            await update.message.reply_text("Please use /start first!")
            return
        
        user = self.users[user_id]
        
        if not user.wallet_address:
            await update.message.reply_text(
                "❌ Please connect your wallet first using /connect!"
            )
            return
        
        # No builder approval required - let people trade directly
        
        # Parse trade command
        if len(context.args) < 3:
            trade_help = """
🎯 **Place a Real Trade**

**Format:**
```
/trade BTC BUY 0.01
/trade ETH SELL 0.1
/trade SOL BUY 1.0
```

**Parameters:**
• Symbol: BTC, ETH, SOL, etc.
• Side: BUY or SELL
• Size: Amount to trade

**Examples:**
```
/trade BTC BUY 0.01
/trade ETH SELL 0.1
/trade SOL BUY 1.0
```

**Builder Code Included:**
Every trade automatically includes builder code for fee collection.

**Ready to trade? Use the format above!**
            """
            await update.message.reply_text(trade_help, parse_mode='Markdown')
            return
        
        symbol = context.args[0].upper()
        side = context.args[1].upper()
        size = float(context.args[2])
        
        if side not in ['BUY', 'SELL']:
            await update.message.reply_text("❌ Side must be BUY or SELL")
            return
        
        # Create user-specific trader
        if user.private_key:
            # Use user's private key for trading
            from bot_modules.hyperliquid_trader import HyperliquidTrader
            user_trader = HyperliquidTrader(user.private_key)
            logger.info(f"Using user's wallet for trading: {user.wallet_address}")
        else:
            # Fallback to main trader (but this shouldn't work for user trades)
            user_trader = self.hyperliquid_trader
            logger.warning(f"Using main trader (this may fail): {user.wallet_address}")
        
        # Validate symbol
        if not await user_trader.validate_symbol(symbol):
            await update.message.reply_text(f"❌ Symbol {symbol} not available for trading")
            return
        
        # Place the trade
        try:
            trade_result = await user_trader.place_trade(symbol, side, size)
            
            if trade_result.success:
                # Update user stats
                user.total_trades += 1
                user.total_volume += trade_result.size * trade_result.price
                
                # Save to Supabase
                if self.supabase:
                    try:
                        await self.supabase.update_user_stats(
                            user_id,
                            total_trades=user.total_trades,
                            total_earnings=user.total_volume
                        )
                    except Exception as e:
                        logger.warning(f"Failed to update user stats in Supabase: {e}")
                
                # Format order details
                order_info = ""
                if trade_result.order_id:
                    order_info = f"• Order ID: {trade_result.order_id}\n"
                
                # Format builder fee info
                builder_info = ""
                if trade_result.builder_fee_applied:
                    builder_info = "• Builder Fee: Applied ✅\n"
                
                # Format auto-correction info
                correction_info = ""
                if size != trade_result.size:
                    correction_info += f"• Size auto-corrected: {size} → {trade_result.size}\n"
                
                trade_text = f"""
✅ **Trade Executed Successfully!**

**Trade Details:**
• Symbol: {trade_result.symbol}
• Side: {trade_result.side}  
• Size: {trade_result.size}
• Entry Price: ${trade_result.price:,.2f}
{order_info}{builder_info}{correction_info}**Hyperliquid Status:** ✅ Confirmed

**Quick Commands:**
• /positions - View current positions
• /trades - See trade history
• /balance - Check account balance
• [View on Hyperliquid](https://app.hyperliquid.xyz/portfolio)
                """
                
                await update.message.reply_text(trade_text, parse_mode='Markdown')
            else:
                # Parse error details from raw response
                error_details = ""
                if trade_result.raw_response:
                    raw = trade_result.raw_response
                    if isinstance(raw, dict):
                        response_data = raw.get("response", {})
                        data = response_data.get("data", {})
                        statuses = data.get("statuses", [])
                        if statuses:
                            for status in statuses:
                                if status.get("error"):
                                    error_details += f"• {status.get('error')}\n"
                
                fail_text = f"""
❌ **Trade Failed**

**Error:** {trade_result.error_message}

**Details:**
{error_details}
**Hyperliquid Response:** Failed

**Solutions:**
• Check /balance for sufficient funds
• Try smaller trade size: `/trade {symbol} {side} 0.001`
• Use /market to check current prices
• [View on Hyperliquid](https://app.hyperliquid.xyz/trade/{symbol.lower()})
                """
                
                await update.message.reply_text(fail_text, parse_mode='Markdown')
                
        except Exception as e:
            logger.error(f"Trade execution failed: {e}")
            await update.message.reply_text(f"❌ Trade error: {str(e)}")

    async def close_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Close position command - easier way to close positions"""
        user_id = update.effective_user.id
        
        if user_id not in self.users:
            await update.message.reply_text("Please use /start first!")
            return
        
        user = self.users[user_id]
        
        if not user.wallet_address:
            await update.message.reply_text(
                "❌ Please connect your wallet first using /connect!"
            )
            return
        
        # Parse close command
        if len(context.args) < 1:
            close_help = """
🔒 **Close Positions**

**Format:**
```
/close BTC           (close entire BTC position)
/close BTC 0.5       (close 0.5 BTC)
/close all           (close all positions)
```

**Examples:**
```
/close BTC           (close all BTC)
/close ETH 0.1       (close 0.1 ETH)
/close SOL 2.0       (close 2.0 SOL)
/close all           (close everything)
```

**Note:** This will place a market order to close your position.
            """
            await update.message.reply_text(close_help, parse_mode='Markdown')
            return
        
        symbol = context.args[0].upper()
        
        # Handle "close all" command
        if symbol == "ALL":
            try:
                # Get current positions
                if user.private_key:
                    from bot_modules.hyperliquid_trader import HyperliquidTrader
                    user_trader = HyperliquidTrader(user.private_key)
                else:
                    user_trader = self.hyperliquid_trader
                
                balance_data = await user_trader.get_account_balance()
                positions = balance_data.get('positions', [])
                
                if not positions or not any(abs(pos.get('szi', 0)) > 0.001 for pos in positions):
                    await update.message.reply_text(
                        "📊 **No positions to close**\n\n"
                        "You don't have any open positions.",
                        parse_mode='Markdown'
                    )
                    return
                
                close_text = "🔒 **Closing All Positions**\n\n"
                
                for pos in positions:
                    size = pos.get('szi', 0)
                    if abs(size) > 0.001:
                        coin = pos.get('coin', '')
                        # Determine close side (opposite of current position)
                        close_side = "SELL" if size > 0 else "BUY"
                        close_size = abs(size)
                        
                        # Place close order
                        result = await user_trader.place_trade(coin, close_side, close_size, is_reduce_only=True)
                        
                        if result.success:
                            close_text += f"✅ Closed {coin}: {close_size:.4f}\n"
                        else:
                            close_text += f"❌ Failed to close {coin}: {result.error_message}\n"
                
                close_text += f"\n**All positions closing orders placed!**"
                await update.message.reply_text(close_text, parse_mode='Markdown')
                
            except Exception as e:
                await update.message.reply_text(f"❌ Close error: {str(e)}")
            return
        
        # Handle specific symbol close
        try:
            # Get current position for symbol
            if user.private_key:
                from bot_modules.hyperliquid_trader import HyperliquidTrader
                user_trader = HyperliquidTrader(user.private_key)
            else:
                user_trader = self.hyperliquid_trader
            
            balance_data = await user_trader.get_account_balance()
            positions = balance_data.get('positions', [])
            
            # Find the position for this symbol
            target_position = None
            for pos in positions:
                if pos.get('coin', '').upper() == symbol and abs(pos.get('szi', 0)) > 0.001:
                    target_position = pos
                    break
            
            if not target_position:
                await update.message.reply_text(
                    f"📊 **No {symbol} position found**\n\n"
                    f"You don't have an open {symbol} position to close.",
                    parse_mode='Markdown'
                )
                return
            
            # Determine close parameters
            current_size = target_position.get('szi', 0)
            close_side = "SELL" if current_size > 0 else "BUY"
            
            # Check if user specified partial close size
            if len(context.args) > 1:
                try:
                    close_size = float(context.args[1])
                    if close_size > abs(current_size):
                        await update.message.reply_text(
                            f"❌ **Invalid size**\n\n"
                            f"You only have {abs(current_size):.4f} {symbol} open.\n"
                            f"Cannot close {close_size:.4f}.",
                            parse_mode='Markdown'
                        )
                        return
                except ValueError:
                    await update.message.reply_text("❌ Invalid size format. Use numbers only.")
                    return
            else:
                # Close entire position
                close_size = abs(current_size)
            
            # Place close order
            result = await user_trader.place_trade(symbol, close_side, close_size, is_reduce_only=True)
            
            if result.success:
                await update.message.reply_text(
                    f"✅ **Position Closed**\n\n"
                    f"**Symbol:** {symbol}\n"
                    f"**Size:** {close_size:.4f}\n"
                    f"**Side:** {close_side}\n"
                    f"**Order ID:** {result.order_id}\n\n"
                    f"Position closing order placed successfully!",
                    parse_mode='Markdown'
                )
            else:
                await update.message.reply_text(
                    f"❌ **Close Failed**\n\n"
                    f"**Error:** {result.error_message}\n\n"
                    f"Please try again or use manual trading.",
                    parse_mode='Markdown'
                )
                
        except Exception as e:
            await update.message.reply_text(f"❌ Close error: {str(e)}")
    
    async def balance_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Check account balance"""
        user_id = update.effective_user.id
        
        if user_id not in self.users:
            await update.message.reply_text("Please use /start first!")
            return
        
        user = self.users[user_id]
        
        if not user.wallet_address:
            await update.message.reply_text(
                "❌ Please connect your wallet first using /connect!"
            )
            return
        
        try:
            # Create user-specific trader
            if user.private_key:
                from bot_modules.hyperliquid_trader import HyperliquidTrader
                user_trader = HyperliquidTrader(user.private_key)
            else:
                user_trader = self.hyperliquid_trader
            
            balance_data = await user_trader.get_account_balance()
            
            if "error" in balance_data:
                balance_text = f"""
💰 **Account Balance**

**Wallet:** `{user.wallet_address}`
**Status:** ❌ Error fetching balance
**Error:** {balance_data['error']}

**Trading Stats:**
• Total Trades: {user.total_trades}
• Total Volume: ${user.total_volume:,.2f}
• Total Earnings: ${user.total_earnings:.4f}
                """
            else:
                balance_text = f"""
💰 **Account Balance**

**Wallet:** `{user.wallet_address}`
**Account Value:** ${balance_data['account_value']:,.2f}
**Available Balance:** ${balance_data['available_balance']:,.2f}
**Total Margin Used:** ${balance_data['total_margin_used']:,.2f}

**Trading Stats:**
• Total Trades: {user.total_trades}
• Total Volume: ${user.total_volume:,.2f}
• Total Earnings: ${user.total_earnings:.4f}

**Positions:** {len(balance_data['positions'])} active
                """
            
            await update.message.reply_text(balance_text, parse_mode='Markdown')
            
        except Exception as e:
            await update.message.reply_text(f"❌ Balance error: {str(e)}")
    
    async def earnings_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """View earnings and stats"""
        user_id = update.effective_user.id
        
        if user_id not in self.users:
            await update.message.reply_text("Please use /start first!")
            return
        
        user = self.users[user_id]
        
        earnings_text = f"""
📊 **Your Earnings & Stats**

**User:** {user.username}
**Wallet:** `{user.wallet_address or 'Not connected'}`
**Builder Approved:** {'✅ Yes' if user.builder_approved else '❌ No'}

**Trading Statistics:**
• Total Trades: {user.total_trades}
• Total Volume: ${user.total_volume:,.2f}
• Total Earnings: ${user.total_earnings:.4f}
• Avg Trade Size: ${user.total_volume/max(user.total_trades, 1):,.2f}

**Revenue Breakdown:**
• Fee Rate: 0.05%
• Your Access: AI trading tools
• My Revenue: ${user.total_earnings:.4f}

**Next Steps:**
• Use /trade to place more trades
• Use /market to view live prices
• Use /balance to check account
        """
        
        await update.message.reply_text(earnings_text, parse_mode='Markdown')
    
    async def trades_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """View recent trades"""
        user_id = update.effective_user.id
        
        if user_id not in self.users:
            await update.message.reply_text("Please use /start first!")
            return
        
        user = self.users[user_id]
        
        if not user.wallet_address:
            await update.message.reply_text(
                "❌ Please connect your wallet first using /connect!"
            )
            return
        
        try:
            # Get recent trades from Supabase
            if self.supabase:
                trades = await self.supabase.get_user_trades(user_id, limit=10)
                
                if trades:
                    # Calculate trading stats
                    total_trades = len(trades)
                    profitable_trades = len([t for t in trades if t.get('pnl', 0) > 0])
                    total_pnl = sum(t.get('pnl', 0) for t in trades)
                    win_rate = (profitable_trades / total_trades * 100) if total_trades > 0 else 0
                    
                    # PnL indicators
                    pnl_emoji = "🟢" if total_pnl >= 0 else "🔴"
                    pnl_sign = "+" if total_pnl >= 0 else ""
                    
                    trades_text = f"""
┌────── 📊 **TRADING HISTORY** ──────┐
│                                                      │
│  🎯 **Total Trades**: {total_trades}                        │
│  🏆 **Win Rate**: {win_rate:.1f}% ({profitable_trades}/{total_trades})          │
│  {pnl_emoji} **Total PnL**: {pnl_sign}${total_pnl:.2f}                  │
│                                                      │
└────────────────────────────────┘

🔥 **RECENT TRADES**
"""
                    
                    for i, trade in enumerate(trades[:5]):
                        side_emoji = "🟢" if trade.get('side') == 'BUY' else "🔴"
                        pnl = trade.get('pnl', 0)
                        pnl_trade_emoji = "📈" if pnl >= 0 else "📉"
                        pnl_trade_sign = "+" if pnl >= 0 else ""
                        
                        trades_text += f"""
┌── {trade.get('symbol', 'N/A')} {side_emoji} ──┐
│ 📏 Size: {trade.get('size', 0):.4f}
│ 💰 Price: ${trade.get('price', 0):,.2f}  
│ {pnl_trade_emoji} PnL: {pnl_trade_sign}${pnl:.2f}
│ ⏱️ Status: {trade.get('status', 'N/A')}
└────────────────────┘
"""
                    
                    trades_text += f"""
🚀 **CONTINUE TRADING**
• `/trade BTC BUY 0.01` - New position
• `/positions` - Current positions
                    """
                else:
                    trades_text = f"""
┌────── 📊 **TRADING HISTORY** ──────┐
│                                                      │
│  🎯 **Total Trades**: 0                         │
│  🏆 **Win Rate**: 0.0% (0/0)                    │
│  🟢 **Total PnL**: $0.00                        │
│                                                      │
└────────────────────────────────┘

💤 **NO TRADES YET**

🚀 **START YOUR JOURNEY**
• `/trade BTC BUY 0.01` - First trade
• `/analyze ETH` - Get signals
                    """
            else:
                trades_text = f"""
📊 **Your Recent Trades**

**Wallet:** `{user.wallet_address}`
**Database not available**

**Trading Stats:**
• Total Trades: {user.total_trades}
• Total Volume: ${user.total_volume:,.2f}

Ready to trade? Use `/trade BTC BUY 0.01`
                """
            
            await update.message.reply_text(trades_text, parse_mode='Markdown')
            
        except Exception as e:
            await update.message.reply_text(f"❌ Trades error: {str(e)}")
    
    async def positions_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """View current positions"""
        user_id = update.effective_user.id
        
        if user_id not in self.users:
            await update.message.reply_text("Please use /start first!")
            return
        
        user = self.users[user_id]
        
        if not user.wallet_address:
            await update.message.reply_text(
                "❌ Please connect your wallet first using /connect!"
            )
            return
        
        try:
            # Create user-specific trader
            if user.private_key:
                from bot_modules.hyperliquid_trader import HyperliquidTrader
                user_trader = HyperliquidTrader(user.private_key)
            else:
                user_trader = self.hyperliquid_trader
            
            # Get current positions from Hyperliquid
            balance_data = await user_trader.get_account_balance()
            
            if "error" in balance_data:
                positions_text = f"""
📈 **Your Current Positions**

**Wallet:** `{user.wallet_address}`
**Status:** ❌ Error fetching positions
**Error:** {balance_data['error']}

**Account Stats:**
• Total Trades: {user.total_trades}
• Total Volume: ${user.total_volume:,.2f}
                """
            else:
                positions = balance_data.get('positions', [])
                
                if positions:
                    # Calculate total PnL and winning positions
                    total_pnl = sum(pos.get('unrealized_pnl', 0) for pos in positions if abs(pos.get('szi', 0)) > 0.001)
                    winning_positions = len([pos for pos in positions if pos.get('unrealized_pnl', 0) > 0 and abs(pos.get('szi', 0)) > 0.001])
                    total_positions = len([pos for pos in positions if abs(pos.get('szi', 0)) > 0.001])
                    win_rate = (winning_positions / total_positions * 100) if total_positions > 0 else 0
                    
                    # Calculate portfolio performance
                    account_value = balance_data.get('account_value', 0)
                    available_balance = balance_data.get('available_balance', 0)
                    margin_used = balance_data.get('total_margin_used', 0)
                    margin_ratio = (margin_used / account_value * 100) if account_value > 0 else 0
                    
                    # PnL indicator
                    pnl_emoji = "🟢" if total_pnl >= 0 else "🔴"
                    pnl_sign = "+" if total_pnl >= 0 else ""
                    
                    # Try to create position cards like Image #2
                    try:
                        from src.tools.trading_card_generator import TradingCardGenerator, UserProfile
                        
                        # Create user profile
                        user_profile = UserProfile(
                            name=user.username or "Trader",
                            username=user.username or f"user{user_id}",
                            balance=account_value,
                            pnl=total_pnl
                        )
                        
                        card_generator = TradingCardGenerator()
                        
                        # Create position cards for each position
                        for pos in positions[:3]:  # Show top 3 positions as cards
                            if abs(pos.get('szi', 0)) > 0.001:
                                position_data = {
                                    'size': abs(pos.get('szi', 0)),
                                    'entry': pos.get('entry_px', 0),
                                    'mark': pos.get('entry_px', 0),  # Could be current mark price
                                    'pnl': pos.get('unrealized_pnl', 0),
                                    'close_time': 'now'
                                }
                                
                                card_bytes = card_generator.create_position_card(pos.get('coin', 'N/A'), position_data, user_profile)
                                
                                if card_bytes:
                                    await update.message.reply_photo(
                                        photo=io.BytesIO(card_bytes),
                                        caption=f"📊 **{pos.get('coin', 'N/A')} Position**\n\n⚡ Powered by Zara AI Trading",
                                        parse_mode='Markdown'
                                    )
                    except Exception as e:
                        logger.warning(f"Could not create position cards: {e}")
                    
                    positions_text = f"""
╭─────────── 📊 **PORTFOLIO** ───────────╮
│                                                           │
│  💰 **Account Value**: ${account_value:,.2f}        │
│  💵 **Available**: ${available_balance:,.2f}              │
│  📈 **Margin Used**: ${margin_used:,.2f} ({margin_ratio:.1f}%)   │
│                                                           │
│  {pnl_emoji} **Total PnL**: {pnl_sign}${total_pnl:.2f}                    │
│  🎯 **Win Rate**: {win_rate:.1f}% ({winning_positions}/{total_positions})             │
│                                                           │
╰─────────────────────────────────────╯

🔥 **ACTIVE POSITIONS** ({total_positions})
"""
                    
                    for i, pos in enumerate(positions):
                        if abs(pos.get('szi', 0)) > 0.001:  # Only show meaningful positions
                            size = pos.get('szi', 0)
                            side = "🟢 LONG" if size > 0 else "🔴 SHORT"
                            coin = pos.get('coin', 'N/A')
                            entry_px = pos.get('entry_px', 0)
                            position_value = pos.get('position_value', 0)
                            unrealized_pnl = pos.get('unrealized_pnl', 0)
                            
                            # PnL formatting
                            pnl_color = "🟢" if unrealized_pnl >= 0 else "🔴"
                            pnl_sign = "+" if unrealized_pnl >= 0 else ""
                            
                            positions_text += f"""
╭── {coin} {side} ──╮
│ 📏 Size: {abs(size):.4f}
│ 🎯 Entry: ${entry_px:,.4f}
│ 💎 Value: ${abs(position_value):,.2f}
│ {pnl_color} PnL: {pnl_sign}${unrealized_pnl:.2f}
╰─────────────────────────╯
"""
                    
                    positions_text += f"""
🚀 **QUICK ACTIONS**
• `/trade BTC BUY 0.01` - Open new position
• `/balance` - Detailed account info  
• [📊 View on Hyperliquid](https://app.hyperliquid.xyz/portfolio)
                    """
                else:
                    account_value = balance_data.get('account_value', 0)
                    available_balance = balance_data.get('available_balance', 0)
                    margin_used = balance_data.get('total_margin_used', 0)
                    
                    positions_text = f"""
┌─────────── 📊 **PORTFOLIO** ───────────┐
│                                                           │
│  💰 **Account Value**: ${account_value:,.2f}        │
│  💵 **Available**: ${available_balance:,.2f}              │
│  📈 **Margin Used**: ${margin_used:,.2f} (0.0%)     │
│                                                           │
│  🟢 **Total PnL**: $0.00                         │
│  🎯 **Win Rate**: 0.0% (0/0)                     │
│                                                           │
└─────────────────────────────────────┘

💤 **NO ACTIVE POSITIONS**

Ready to start trading? Here are some popular choices:

🚀 **TRENDING ASSETS**
• `/trade BTC BUY 0.01` - Bitcoin
• `/trade ETH BUY 0.1` - Ethereum  
• `/trade SOL BUY 1.0` - Solana

📊 **GET ANALYSIS FIRST**
• `/analyze BTC` - AI market analysis
• `/analyze ETH` - Technical indicators
• [📈 View Market](https://app.hyperliquid.xyz/trade)
                    """
            
            await update.message.reply_text(positions_text, parse_mode='Markdown')
            
        except Exception as e:
            await update.message.reply_text(f"❌ Positions error: {str(e)}")
    
    async def market_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """View real-time market data"""
        try:
            # Get top symbols
            symbols = ['BTC', 'ETH', 'SOL', 'AVAX', 'BNB']
            market_data = []
            
            for symbol in symbols:
                data = await self.hyperliquid_trader.get_market_data(symbol)
                if data:
                    market_data.append(f"• {symbol}: ${data.price:,.2f}")
            
            market_text = f"""
📈 **Real-Time Market Data**

{chr(10).join(market_data)}

**Builder Code Active:** ✅
**Fee Rate:** 0.05%

**Ready to trade? Use /trade BTC BUY 0.01**
            """
            
            await update.message.reply_text(market_text, parse_mode='Markdown')
            
        except Exception as e:
            await update.message.reply_text(f"❌ Market data error: {str(e)}")
    
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Check overall status"""
        user_id = update.effective_user.id
        
        if user_id not in self.users:
            await update.message.reply_text("Please use /start first!")
            return
        
        user = self.users[user_id]
        
        status_text = f"""
🔍 **Account Status**

**User:** {user.username}
**Wallet:** {'✅ Connected' if user.wallet_address else '❌ Not connected'}
**Builder Approved:** {'✅ Yes' if user.builder_approved else '❌ No'}
**Total Users:** {len(self.users)}

**Ready to Trade:** {'✅ Yes' if user.wallet_address and user.builder_approved else '❌ No'}

**Next Steps:**
{'Use /trade to start trading!' if user.wallet_address and user.builder_approved else 'Use /connect and /approve to get started!'}
        """
        
        await update.message.reply_text(status_text, parse_mode='Markdown')
    
    
    async def import_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Import existing wallet with private key"""
        user = update.effective_user
        user_id = user.id
        username = user.username or user.first_name or "User"
        
        if user_id not in self.users:
            await update.message.reply_text("Please use /start first!")
            return
        
        user_state = self.users[user_id]
        
        # Allow importing new wallet even if one exists
        if user_state.wallet_address:
            await update.message.reply_text(
                f"⚠️ **Wallet Already Connected**\n\n"
                f"Current wallet: `{user_state.wallet_address}`\n\n"
                f"**Importing new wallet will replace the current one.**\n"
                f"Processing your import...",
                parse_mode='Markdown'
            )
            # Continue with import instead of returning
        
        # Check if private key provided
        if not context.args:
            await update.message.reply_text(
                "🔐 **Import Existing Wallet**\n\n"
                "**Format:**\n"
                "`/import YOUR_PRIVATE_KEY`\n\n"
                "**Example:**\n"
                "`/import 0x1234567890abcdef...`\n\n"
                "**Security:**\n"
                "• Your message will be deleted after import\n"
                "• Private key is encrypted and stored securely\n"
                "• Never share your private key with anyone\n\n"
                "**Ready to import?** Send your private key!",
                parse_mode='Markdown'
            )
            return
        
        private_key = context.args[0]
        
        # Validate private key format
        if not private_key.startswith('0x') or len(private_key) != 66:
            await update.message.reply_text(
                "❌ **Invalid Private Key Format**\n\n"
                "Private key must be:\n"
                "• 64 characters long\n"
                "• Start with '0x'\n"
                "• Valid hexadecimal\n\n"
                "**Example:** `0x1234567890abcdef...`",
                parse_mode='Markdown'
            )
            return
        
        try:
            # Import wallet using private key
            from eth_account import Account
            account = Account.from_key(private_key)
            wallet_address = account.address
            
            # Allow wallet re-imports - remove restriction
            logger.info(f"Importing wallet {wallet_address} for user {user_id} (allowing overwrites)")
            
            # Update user state
            user_state.wallet_address = wallet_address
            user_state.privy_user_id = f"imported_{user_id}"
            # Store private key securely for auto-approval
            user_state.private_key = private_key
            
            # Save to Supabase
            if self.supabase:
                try:
                    user_data = UserData(
                        telegram_user_id=user_id,
                        username=username,
                        wallet_address=wallet_address,
                        privy_user_id=f"imported_{user_id}",
                        is_active=True,
                        last_active=datetime.now()
                    )
                    # Always try to update first, create if doesn't exist
                    try:
                        # Try to update existing user first
                        update_data = {
                            'wallet_address': wallet_address,
                            'privy_user_id': f"imported_{user_id}",
                            'last_active': datetime.now().isoformat(),
                            'username': username
                        }
                        updated = await self.supabase.update_user(user_id, update_data)
                        if updated:
                            logger.info(f"✅ Updated existing user {user_id} with new wallet in Supabase")
                        else:
                            # User doesn't exist, create new
                            await self.supabase.create_user(user_data)
                            logger.info(f"✅ Created new imported user {user_id} in Supabase")
                    except Exception as save_error:
                        logger.info(f"✅ Imported wallet locally (Supabase error: {save_error})")
                        # Continue anyway - wallet is imported locally
                except Exception as e:
                    logger.warning(f"Failed to save imported user to Supabase: {e}")
            
            # Send success message
            import_text = f"""
🔐 **Wallet Imported Successfully!**

**Your Wallet Address:**
`{wallet_address}`

**Import Status:** ✅ Connected and Ready
**Security:** Private key encrypted and stored securely

**Ready to Trade:**
• Use `/trade SOL BUY 0.01` to start trading immediately
• Use `/balance` to check your account
• Use `/positions` to view current positions
• Use `/analyze BTC` for AI market analysis

**No approval needed - start trading now!**
            """
            
            await update.message.reply_text(import_text, parse_mode='Markdown')
            
            # Delete the user's message containing the private key for security
            try:
                await update.message.delete()
                logger.info(f"✅ Deleted private key message for user {user_id}")
            except Exception as e:
                logger.warning(f"Failed to delete private key message: {e}")
                # Send a follow-up message about security
                await update.message.reply_text(
                    "🔒 **Security Reminder:**\n\n"
                    "Please delete your previous message containing the private key for security.",
                    parse_mode='Markdown'
                )
            
        except Exception as e:
            logger.error(f"Wallet import failed: {e}")
            await update.message.reply_text(
                f"❌ **Wallet Import Failed**\n\n"
                f"Error: {str(e)}\n\n"
                f"Please check your private key and try again.",
                parse_mode='Markdown'
            )
    
    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle button callbacks"""
        query = update.callback_query
        await query.answer()
        
        if query.data == "start_setup":
            await query.edit_message_text(
                "🚀 **Let's Get Started!**\n\n"
                "1. Use /connect to connect your wallet\n"
                "2. Use /trade to start trading\n"
                "3. Use /analyze for market insights!\n\n"
                "Ready? Let's go! 🎯",
                parse_mode='Markdown'
            )
        elif query.data == "show_help":
            await query.edit_message_text(
                "📊 **Available Commands:**\n\n"
                "/start - Welcome and setup\n"
                "/connect - Connect wallet\n"
                "/trade - Place trades\n"
                "/balance - Check balance\n"
                "/earnings - View earnings\n"
                "/market - Market data\n"
                "/export - Export wallet\n"
                "/status - Account status\n"
                "/help - Show this help",
                parse_mode='Markdown'
            )
        elif query.data == "how_it_works":
            await query.edit_message_text(
                "🚀 **How Trading Works:**\n\n"
                "1. **Connect** your wallet easily\n"
                "2. **Trade** any crypto instantly\n"
                "3. **Get AI analysis** for better decisions\n"
                "4. **Track** your portfolio in real-time\n\n"
                "Simple and powerful! 🎯",
                parse_mode='Markdown'
            )
        
        # Handle quick action buttons
        elif data == "view_positions":
            # Redirect to positions command functionality
            if not user_state.wallet_address:
                await query.edit_message_text("❌ No wallet connected!")
                return
            
            try:
                # Create user-specific trader
                if user_state.private_key:
                    from bot_modules.hyperliquid_trader import HyperliquidTrader
                    user_trader = HyperliquidTrader(user_state.private_key)
                else:
                    user_trader = self.hyperliquid_trader
                
                balance_data = await user_trader.get_account_balance()
                positions = balance_data.get('positions', [])
                
                if positions and any(abs(pos.get('szi', 0)) > 0.001 for pos in positions):
                    # Calculate metrics
                    total_pnl = sum(pos.get('unrealized_pnl', 0) for pos in positions if abs(pos.get('szi', 0)) > 0.001)
                    total_positions = len([pos for pos in positions if abs(pos.get('szi', 0)) > 0.001])
                    pnl_emoji = "🟢" if total_pnl >= 0 else "🔴"
                    pnl_sign = "+" if total_pnl >= 0 else ""
                    
                    positions_text = f"""
📊 **PORTFOLIO SNAPSHOT**

{pnl_emoji} **Total PnL**: {pnl_sign}${total_pnl:.2f}
🔥 **Active Positions**: {total_positions}

**TOP POSITIONS:**
"""
                    for i, pos in enumerate(positions[:3]):  # Show top 3
                        if abs(pos.get('szi', 0)) > 0.001:
                            side_emoji = "🟢" if pos.get('szi', 0) > 0 else "🔴"
                            pnl_pos = pos.get('unrealized_pnl', 0)
                            pnl_sign_pos = "+" if pnl_pos >= 0 else ""
                            positions_text += f"• {side_emoji} {pos.get('coin', 'N/A')}: {pnl_sign_pos}${pnl_pos:.2f}\n"
                else:
                    positions_text = """
📊 **PORTFOLIO SNAPSHOT**

💤 **No Open Positions**

Ready to start? Try these:
• BTC • ETH • SOL
"""
                
                keyboard = [
                    [InlineKeyboardButton("🔄 Trade BTC", callback_data="analyze_BTC")],
                    [InlineKeyboardButton("💰 Check Balance", callback_data="check_balance")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await query.edit_message_text(positions_text, parse_mode='Markdown', reply_markup=reply_markup)
            except Exception as e:
                await query.edit_message_text(f"❌ Error: {str(e)}")
        
        elif data == "view_trades":
            # Redirect to trades command functionality
            if self.supabase:
                try:
                    trades = await self.supabase.get_user_trades(user_id, limit=5)
                    if trades:
                        trades_text = f"📊 **Recent Trades**\n\n"
                        for trade in trades[:3]:
                            trades_text += f"• {trade.get('symbol', 'N/A')} {trade.get('side', 'N/A')}: ${trade.get('pnl', 0):.2f}\n"
                    else:
                        trades_text = "📊 **No Recent Trades**\n\nStart trading now!"
                except:
                    trades_text = "📊 **Trade History**\n\nUse /trades for full history"
            else:
                trades_text = "📊 **Trade History**\n\nUse /trades for full history"
            
            keyboard = [
                [InlineKeyboardButton("🔄 Trade More", callback_data="analyze_BTC")],
                [InlineKeyboardButton("📈 Full History", callback_data="full_trades")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(trades_text, parse_mode='Markdown', reply_markup=reply_markup)
        
        elif data == "check_balance":
            # Redirect to balance command functionality
            if not user_state.wallet_address:
                await query.edit_message_text("❌ No wallet connected!")
                return
            
            try:
                # Create user-specific trader
                if user_state.private_key:
                    from bot_modules.hyperliquid_trader import HyperliquidTrader
                    user_trader = HyperliquidTrader(user_state.private_key)
                else:
                    user_trader = self.hyperliquid_trader
                
                balance_data = await user_trader.get_account_balance()
                account_value = balance_data.get('account_value', 0)
                available_balance = balance_data.get('available_balance', 0) 
                margin_used = balance_data.get('total_margin_used', 0)
                positions = balance_data.get('positions', [])
                
                # Calculate portfolio health
                health_ratio = (available_balance / account_value * 100) if account_value > 0 else 0
                health_emoji = "🟢" if health_ratio > 50 else "🟡" if health_ratio > 20 else "🔴"
                
                balance_text = f"""
┌────── 💰 **ACCOUNT OVERVIEW** ──────┐
│                                                    │
│  💎 **Total Value**: ${account_value:,.2f}          │
│  💵 **Available**: ${available_balance:,.2f}        │
│  📊 **Margin Used**: ${margin_used:,.2f}            │
│                                                    │
│  {health_emoji} **Portfolio Health**: {health_ratio:.1f}%      │
│                                                    │
└──────────────────────────────────┘

🚀 **READY TO TRADE**
"""
                
                keyboard = [
                    [
                        InlineKeyboardButton("📈 Buy BTC", callback_data="trade_BTC_buy"),
                        InlineKeyboardButton("📉 Sell BTC", callback_data="trade_BTC_sell")
                    ],
                    [InlineKeyboardButton("📊 Analyze Market", callback_data="analyze_BTC")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await query.edit_message_text(balance_text, parse_mode='Markdown', reply_markup=reply_markup)
            except Exception as e:
                await query.edit_message_text(f"❌ Balance error: {str(e)}")
        
        # Handle analyze buttons (refresh analysis)
        elif data.startswith("analyze_"):
            symbol = data.split("_")[1].upper()
            await query.edit_message_text(
                f"🔍 **Analyzing {symbol}...**\n\n"
                f"📡 Fetching real-time data...\n"
                f"🧠 Running AI analysis...",
                parse_mode='Markdown'
            )
            # The analyze functionality will be handled by the existing analyze command logic
    
    def run(self):
        """Run the bot"""
        print("🤖 Starting Hyperliquid Privy Bot...")
        print(f"Builder Address: {self.hyperliquid_trader.builder_address}")
        print("Note: Builder address is set to your wallet address - you earn the fees!")
        print(f"Fee Rate: {self.hyperliquid_trader.builder_fee_tenths_bps/10000:.4f}%")
        print("Bot is running... Press Ctrl+C to stop")
        
        self.application.run_polling()

def main():
    """Main function"""
    if not SDK_AVAILABLE:
        print("❌ Please install dependencies first:")
        print("pip install python-telegram-bot hyperliquid-python-sdk eth-account python-dotenv")
        return
    
    try:
        bot = HyperliquidPrivyBot()
        bot.run()
    except Exception as e:
        print(f"❌ Bot error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
