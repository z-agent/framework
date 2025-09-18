"""
Refactored Hyperliquid Auto Trading Bot
Modular structure with separated components
"""

import asyncio
import logging
import os
from typing import Dict, Optional, Any, List
from dataclasses import dataclass, field

# Import bot modules
from bot_modules.callback_handler import CallbackQueryHandler
from bot_modules.command_handlers import CommandHandlers
from bot_modules.wallet_manager import WalletManager
from bot_modules.ui_components import UIComponents
import requests
import base64

# Telegram imports
try:
    from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
    from telegram.ext import Application, CommandHandler, CallbackQueryHandler as TelegramCallbackQueryHandler, ContextTypes
    from hyperliquid.info import Info
    from hyperliquid.utils import constants
    from hyperliquid.exchange import Exchange
    SDK_AVAILABLE = True
except ImportError as e:
    print(f"❌ Missing dependencies: {e}")
    SDK_AVAILABLE = False

# Supabase integration (optional)
try:
    from supabase_trading_service import get_trading_service, UserData, create_user, get_user, update_user
    SUPABASE_IMPORT_SUCCESS = True
except Exception as e:
    print(f"⚠️ Supabase import failed: {e}")
    SUPABASE_IMPORT_SUCCESS = False

# Analysis tools
try:
    from src.tools.ivishx_improved import ImprovedIvishXAnalyzeTool
    ANALYSIS_AVAILABLE = True
except ImportError:
    ANALYSIS_AVAILABLE = False
    print("⚠️ Analysis tools not available")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class UserState:
    """User state data class with safety controls"""
    # Wallet and authentication
    wallet_address: Optional[str] = None
    privy_user_id: Optional[str] = None
    session_signer: Optional[Any] = None
    
    # Trading controls - DRY mode by default
    auto_trade_enabled: bool = False
    trading_mode: str = "DRY"  # DRY | LIVE
    risk_per_trade: float = 0.01  # 1% of balance per trade (conservative)
    max_position_size: float = 0.05  # 5% max position (conservative)
    min_confidence: int = 70  # Minimum confidence level for trades
    
    # Safety controls - Kill switches
    daily_pnl: float = 0.0  # Daily P&L tracking
    consecutive_losses: int = 0  # Consecutive loss counter
    last_trade_timestamp: float = 0.0  # Last trade timestamp
    min_trade_interval_s: int = 180  # 3 minutes minimum between trades
    daily_pnl_stop: float = -0.015  # -1.5% daily stop loss
    consecutive_losses_stop: int = 3  # Stop after 3 consecutive losses
    
    # Stop loss and take profit caps
    sl_pct: float = 0.008  # 0.8% stop loss
    tp_pct: float = 0.012  # 1.2% take profit
    
    # Trading history
    total_trades: int = 0
    total_earnings: float = 0.0
    total_pnl: float = 0.0
    trades: List[Dict] = field(default_factory=list)
    
    # Security - disable wallet export
    wallet_export_enabled: bool = False  # Disabled for security
    read_only_pubkey: Optional[str] = None  # Show read-only public key only


class PrivyRESTClient:
    """REST API client for Privy following the official documentation"""
    
    def __init__(self, app_id: str, app_secret: str):
        self.app_id = app_id
        self.app_secret = app_secret
        self.base_url = "https://api.privy.io/v1"
        
        # Create Basic Auth header as per documentation
        credentials = f"{app_id}:{app_secret}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        self.headers = {
            "Authorization": f"Basic {encoded_credentials}",
            "privy-app-id": app_id,
            "Content-Type": "application/json"
        }
    
    def create_user(self, linked_accounts):
        """Create a user with linked accounts"""
        url = f"{self.base_url}/users"
        data = {"linkedAccounts": linked_accounts}
        
        response = requests.post(url, headers=self.headers, json=data)
        response.raise_for_status()
        return response.json()
    
    def create_wallet(self, chainType, owner, additionalSigners=None, privateKey=None):
        """Create a wallet for a user"""
        url = f"{self.base_url}/wallets"
        data = {
            "chainType": chainType,
            "owner": owner
        }
        
        if additionalSigners:
            data["additionalSigners"] = additionalSigners
        if privateKey:
            data["privateKey"] = privateKey
            
        response = requests.post(url, headers=self.headers, json=data)
        response.raise_for_status()
        return response.json()
    
    def get_user_by_telegram_id(self, telegram_user_id):
        """Get user by Telegram user ID"""
        url = f"{self.base_url}/users"
        params = {"linkedAccountType": "telegram", "linkedAccountId": str(telegram_user_id)}
        
        response = requests.get(url, headers=self.headers, params=params)
        response.raise_for_status()
        users = response.json()
        return users[0] if users else None


class HyperliquidTradingBot:
    """Main trading bot class with modular architecture"""
    
    def __init__(self):
        """Initialize the bot with modular components"""
        if not SDK_AVAILABLE:
            raise ImportError("Required dependencies not available")
        
        # Bot configuration
        self.bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        print(f"🔑 Bot token: {self.bot_token}")
        # Try both naming conventions for Privy credentials
        self.privy_app_id = os.getenv('PRIVY_APP_ID')
        self.privy_app_secret = os.getenv('PRIVY_APP_SECRET')
        
        if not self.bot_token:
            self.bot_token = "8111284628:AAHq4vWeCwADYJC-26DKe7OWorLra7hckvA"
            # raise ValueError("TELEGRAM_BOT_TOKEN environment variable is required")
        
        # Initialize application
        self.application = Application.builder().token(self.bot_token).build()
        
        # User data storage
        self.users: Dict[int, UserState] = {}
        
        # Auto-trading state
        self.auto_trading_active = False
        
        # Initialize Privy client using REST API
        self.privy_client = None
        if self.privy_app_id and self.privy_app_secret:
            try:
                self.privy_client = PrivyRESTClient(
                    app_id=self.privy_app_id,
                    app_secret=self.privy_app_secret
                )
                logger.info("✅ Privy client initialized")
            except Exception as e:
                logger.error(f"❌ Failed to initialize Privy client: {e}")
                self.privy_client = None
        else:
            logger.warning("⚠️ Privy credentials not configured - wallet features disabled")
            logger.warning("📝 Set PRIVY_APP_ID and PRIVY_APP_SECRET environment variables to enable wallet features")
        
        # Initialize Supabase service
        self.supabase_service = None
        try:
            from supabase_trading_service import SupabaseTradingService
            self.supabase_service = SupabaseTradingService()
            logger.info("✅ Supabase initialized - user data will persist")
        except Exception as e:
            logger.warning(f"⚠️ Supabase initialization failed: {e}")
            logger.warning("📝 Supabase disabled - bot will work without persistence")
            self.supabase_service = None
        
        # Initialize analysis tools
        if ANALYSIS_AVAILABLE:
            self.ivishx_tool = ImprovedIvishXAnalyzeTool()
            logger.info(f"✅ Analysis tools initialized - SAFE MODE {self.ivishx_tool}")
        else:
            self.ivishx_tool = None
            logger.warning("⚠️ Analysis tools not available")
        logger.info("⚠️  No trading connection until user connects wallet")
        
        # Initialize modular components
        self.callback_handler = CallbackQueryHandler(self)
        self.command_handlers = CommandHandlers(self)
        self.wallet_manager = WalletManager(self)
        
        # Setup handlers
        self._setup_handlers()
        
        logger.info("🚀 Hyperliquid Trading Bot initialized successfully!")
    
    def allowed_to_trade(self, user: UserState) -> tuple[bool, str]:
        """Check if user is allowed to trade based on safety controls"""
        import time
        
        # Check daily PnL stop
        if user.daily_pnl <= user.daily_pnl_stop:
            return False, "daily_pnl_stop_hit"
        
        # Check consecutive losses stop
        if user.consecutive_losses >= user.consecutive_losses_stop:
            return False, "consecutive_losses_stop_hit"
        
        # Check minimum trade interval
        if time.time() - user.last_trade_timestamp < user.min_trade_interval_s:
            return False, "min_interval"
        
        return True, "ok"
    
    def calculate_position_size(self, user: UserState, balance: float) -> float:
        """Calculate position size based on risk management"""
        return balance * user.risk_per_trade
    
    def calculate_sl_tp(self, user: UserState, price: float, side: str) -> tuple[float, float]:
        """Calculate stop loss and take profit levels"""
        if side.lower() == "buy":
            sl = price * (1 - user.sl_pct)
            tp = price * (1 + user.tp_pct)
        else:  # sell
            sl = price * (1 + user.sl_pct)
            tp = price * (1 - user.tp_pct)
        
        return sl, tp
    
    def update_trade_stats(self, user: UserState, trade_pnl: float):
        """Update trading statistics after a trade"""
        import time
        
        user.last_trade_timestamp = time.time()
        user.total_trades += 1
        user.daily_pnl += trade_pnl
        user.total_pnl += trade_pnl
        
        if trade_pnl > 0:
            user.consecutive_losses = 0  # Reset on profit
        else:
            user.consecutive_losses += 1
    
    async def execute_hardened_trade(self, user: UserState, symbol: str, side: str, price: float, balance: float) -> dict:
        """Execute trade with all safety controls enabled"""
        import time
        
        # Check if trading is allowed
        allowed, reason = self.allowed_to_trade(user)
        if not allowed:
            return {
                "accepted": False,
                "reason": reason,
                "mode": user.trading_mode
            }
        
        # Calculate position size and SL/TP
        notional = self.calculate_position_size(user, balance)
        sl, tp = self.calculate_sl_tp(user, price, side)
        
        # Create trade order
        order = {
            "symbol": symbol,
            "side": side,
            "notional": notional,
            "price": price,
            "sl": sl,
            "tp": tp,
            "timestamp": time.time()
        }
        
        if user.trading_mode == "DRY":
            # Simulate trade in DRY mode
            logger.info(f"🔍 DRY MODE: Would execute {side} {symbol} at ${price:.4f}")
            logger.info(f"   Notional: ${notional:.2f}, SL: ${sl:.4f}, TP: ${tp:.4f}")
            
            # Simulate trade result
            simulated_pnl = (tp - price) / price * notional if side.lower() == "buy" else (price - tp) / price * notional
            self.update_trade_stats(user, simulated_pnl)
            
            return {
                "accepted": True,
                "mode": "DRY",
                "order": order,
                "simulated_pnl": simulated_pnl
            }
        else:
            # LIVE mode - execute real trade
            try:
                # TODO: Implement real Hyperliquid API call here
                logger.warning("🚨 LIVE MODE: Real trading not implemented yet")
                return {
                    "accepted": False,
                    "reason": "live_mode_not_implemented",
                    "mode": "LIVE"
                }
            except Exception as e:
                logger.error(f"❌ Trade execution failed: {e}")
                return {
                    "accepted": False,
                    "reason": "execution_error",
                    "mode": "LIVE",
                    "error": str(e)
                }
    
    async def show_public_key_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show read-only public key (wallet export disabled for security)"""
        user_id = update.effective_user.id
        
        if user_id not in self.users:
            await update.message.reply_text(
                "❌ **No Account Found**\n\n"
                "Please use `/start` to create an account first.",
                parse_mode='Markdown'
            )
            return
        
        user = self.users[user_id]
        
        if not user.wallet_address:
            await update.message.reply_text(
                "❌ **No Wallet Connected**\n\n"
                "Please use `/create` or `/import` to set up a wallet first.",
                parse_mode='Markdown'
            )
            return
        
        # Show read-only public key
        await update.message.reply_text(
            f"🔑 **Read-Only Public Key**\n\n"
            f"**Wallet Address:** `{user.wallet_address}`\n\n"
            f"⚠️ **Security Notice:**\n"
            f"• Wallet export is disabled for security\n"
            f"• This is a read-only public key\n"
            f"• Private keys are never exposed\n"
            f"• Use `/rotate` to rotate signer if needed\n\n"
            f"✅ **Safe for sharing** - This address can be used to receive funds",
            parse_mode='Markdown'
        )
    
    async def show_trading_status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show trading status and safety controls"""
        user_id = update.effective_user.id
        
        if user_id not in self.users:
            await update.message.reply_text(
                "❌ **No Account Found**\n\n"
                "Please use `/start` to create an account first.",
                parse_mode='Markdown'
            )
            return
        
        user = self.users[user_id]
        import time
        
        # Check trading status
        allowed, reason = self.allowed_to_trade(user)
        time_since_last = time.time() - user.last_trade_timestamp
        
        # Status indicators
        status_emoji = "🟢" if allowed else "🔴"
        mode_emoji = "🔍" if user.trading_mode == "DRY" else "🚨"
        
        status_text = f"""
{status_emoji} **Trading Status**

**Mode:** {mode_emoji} {user.trading_mode}
**Auto-Trading:** {'✅ Enabled' if user.auto_trade_enabled else '❌ Disabled'}
**Trading Allowed:** {'✅ Yes' if allowed else '❌ No'}

**Safety Controls:**
• Risk per Trade: {user.risk_per_trade*100:.1f}%
• Max Position: {user.max_position_size*100:.1f}%
• Stop Loss: {user.sl_pct*100:.1f}%
• Take Profit: {user.tp_pct*100:.1f}%
• Min Interval: {user.min_trade_interval_s}s

**Kill Switches:**
• Daily PnL: {user.daily_pnl*100:.2f}% (Stop: {user.daily_pnl_stop*100:.1f}%)
• Consecutive Losses: {user.consecutive_losses}/{user.consecutive_losses_stop}
• Last Trade: {int(time_since_last/60):.0f}m ago

**Trading Stats:**
• Total Trades: {user.total_trades}
• Total PnL: {user.total_pnl*100:.2f}%
• Daily PnL: {user.daily_pnl*100:.2f}%
"""
        
        if not allowed:
            status_text += f"\n⚠️ **Blocked:** {reason.replace('_', ' ').title()}"
        
        await update.message.reply_text(status_text, parse_mode='Markdown')
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show help with safety features"""
        help_text = """
🚀 **Hyperliquid Trading Bot - Hardened Edition**

🔍 **DRY MODE BY DEFAULT** - All trades are simulated until you enable LIVE mode

**💰 Wallet & Security**
• `/create` - Create secure Privy wallet
• `/import <key>` - Import existing wallet
• `/pubkey` - Show read-only public key (export disabled for security)
• `/balance` - Check account balance

**📊 Trading & Analysis**
• `/analyze <symbol>` - Analyze market signals
• `/trade <symbol> <side> <amount>` - Execute trade (DRY mode)
• `/status` - Show trading status and safety controls
• `/positions` - View open positions
• `/trades` - View trade history

**🛡️ Safety Features**
• **Kill Switches**: Daily PnL stop (-1.5%), Consecutive loss stop (3)
• **Position Limits**: 1% risk per trade, 5% max position
• **Time Controls**: 3-minute minimum between trades
• **Stop Loss/Take Profit**: 0.8% SL, 1.2% TP caps
• **DRY Mode**: All trades simulated by default

**⚙️ Commands**
• `/auto` - Toggle auto-trading
• `/help` - Show this help
• `/start` - Initialize bot

**🔒 Security Notice**
• Wallet export is disabled for security
• Private keys are never exposed
• All trades start in DRY mode
• Use `/status` to check safety controls
"""
        await update.message.reply_text(help_text, parse_mode='Markdown')
    
    def _setup_handlers(self):
        """Setup bot command handlers"""
        # Command handlers
        self.application.add_handler(CommandHandler("start", self.command_handlers.start_command))
        self.application.add_handler(CommandHandler("help", self.command_handlers.help_command))
        self.application.add_handler(CommandHandler("auto", self.command_handlers.auto_command))
        self.application.add_handler(CommandHandler("analyze", self.command_handlers.analyze_command))
        self.application.add_handler(CommandHandler("balance", self.command_handlers.balance_command))
        self.application.add_handler(CommandHandler("positions", self.command_handlers.positions_command))
        self.application.add_handler(CommandHandler("trades", self.command_handlers.trades_command))
        self.application.add_handler(CommandHandler("status", self.show_trading_status_command))
        
        # Wallet management commands
        self.application.add_handler(CommandHandler("create", self.wallet_manager.create_wallet))
        self.application.add_handler(CommandHandler("import", self.wallet_manager.import_wallet))
        self.application.add_handler(CommandHandler("pubkey", self.show_public_key_command))  # Show read-only pubkey
        self.application.add_handler(CommandHandler("wallet", self._wallet_management_command))
        
        # Additional commands (delegated to original methods for now)
        self.application.add_handler(CommandHandler("connect", self.connect_command))
        self.application.add_handler(CommandHandler("trade", self.trade_command))
        self.application.add_handler(CommandHandler("earnings", self.earnings_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("verify", self.verify_command))
        self.application.add_handler(CommandHandler("fills", self.fills_command))
        self.application.add_handler(CommandHandler("close", self.close_command))
        self.application.add_handler(CommandHandler("market", self.market_command))
        self.application.add_handler(CommandHandler("risk", self.risk_command))
        self.application.add_handler(CommandHandler("portfolio", self.portfolio_command))
        self.application.add_handler(CommandHandler("pnl", self.pnl_command))
        self.application.add_handler(CommandHandler("builderfees", self.builder_fees_command))
        self.application.add_handler(CommandHandler("revenue", self.revenue_command))
        self.application.add_handler(CommandHandler("withdraw", self.withdraw_command))
        self.application.add_handler(CommandHandler("bridge", self.bridge_command))
        self.application.add_handler(CommandHandler("aggressive", self.aggressive_command))
        self.application.add_handler(CommandHandler("transact", self.transact_command))
        
        # Callback query handler
        self.application.add_handler(TelegramCallbackQueryHandler(self.callback_handler.handle_callback_query))
    
    async def _wallet_management_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Wallet management command"""
        user_id = update.effective_user.id
        
        if user_id not in self.users:
            await update.message.reply_text(
                "❌ Please use <code>/start</code> first!",
                parse_mode='HTML'
            )
            return
        
        user = self.users[user_id]
        
        if not user.wallet_address:
            # No wallet - show setup options
            wallet_text = """
🔐 <b>Wallet Management</b>

<b>No wallet connected</b>

<b>Get Started:</b>
• Create a new wallet
• Import existing wallet
• View available features
            """
            
            reply_markup = UIComponents.get_wallet_setup_keyboard()
            
            await update.message.reply_text(
                wallet_text,
                parse_mode='HTML',
                reply_markup=reply_markup
            )
        else:
            # Has wallet - show management options
            wallet_text = f"""
🔐 <b>Wallet Management</b>

<b>Wallet Address:</b>
<code>{user.wallet_address[:10]}...{user.wallet_address[-8:]}</code>

<b>Status:</b> {'✅ Connected' if user.wallet_address else '❌ Not Connected'}
<b>Auto-Trading:</b> {'🟢 ON' if user.auto_trade_enabled else '🔴 OFF'}

<b>Available Actions:</b>
• Backup wallet
• Check balance
• Enable auto-trading
• Delete wallet
            """
            
            reply_markup = UIComponents.get_wallet_management_keyboard()
            
            await update.message.reply_text(
                wallet_text,
                parse_mode='HTML',
                reply_markup=reply_markup
            )
    
    # Placeholder methods for commands not yet refactored
    async def connect_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Connect command - placeholder"""
        await update.message.reply_text(
            "🔗 <b>Connect Wallet</b>\n\n"
            "Use <code>/create</code> to create a new wallet or <code>/import</code> to import an existing one.",
            parse_mode='HTML'
        )
    
    async def trade_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Trade command - placeholder"""
        await update.message.reply_text(
            "📈 <b>Trading</b>\n\n"
            "Trading functionality is being refactored. Please use the buttons in the interface for now.",
            parse_mode='HTML'
        )
    
    async def earnings_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Earnings command - placeholder"""
        await update.message.reply_text(
            "💰 <b>Earnings</b>\n\n"
            "Earnings functionality is being refactored. Please use the buttons in the interface for now.",
            parse_mode='HTML'
        )
    
    async def verify_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Verify command - placeholder"""
        await update.message.reply_text(
            "✅ <b>Verify</b>\n\n"
            "Verification functionality is being refactored.",
            parse_mode='HTML'
        )
    
    async def fills_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Fills command - placeholder"""
        await update.message.reply_text(
            "📋 <b>Fills</b>\n\n"
            "Fills functionality is being refactored.",
            parse_mode='HTML'
        )
    
    async def close_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Close command - placeholder"""
        await update.message.reply_text(
            "🔄 <b>Close Position</b>\n\n"
            "Close position functionality is being refactored.",
            parse_mode='HTML'
        )
    
    async def market_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Market command - placeholder"""
        await update.message.reply_text(
            "📊 <b>Market Data</b>\n\n"
            "Market data functionality is being refactored.",
            parse_mode='HTML'
        )
    
    async def risk_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Risk command - placeholder"""
        await update.message.reply_text(
            "⚙️ <b>Risk Settings</b>\n\n"
            "Risk settings functionality is being refactored.",
            parse_mode='HTML'
        )
    
    async def portfolio_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Portfolio command - placeholder"""
        await update.message.reply_text(
            "📊 <b>Portfolio</b>\n\n"
            "Portfolio functionality is being refactored.",
            parse_mode='HTML'
        )
    
    async def pnl_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """P&L command - placeholder"""
        await update.message.reply_text(
            "📈 <b>P&L</b>\n\n"
            "P&L functionality is being refactored.",
            parse_mode='HTML'
        )
    
    async def builder_fees_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Builder fees command - placeholder"""
        await update.message.reply_text(
            "🏗️ <b>Builder Fees</b>\n\n"
            "Builder fees functionality is being refactored.",
            parse_mode='HTML'
        )
    
    async def revenue_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Revenue command - placeholder"""
        await update.message.reply_text(
            "💰 <b>Revenue</b>\n\n"
            "Revenue functionality is being refactored.",
            parse_mode='HTML'
        )
    
    async def withdraw_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Withdraw command - placeholder"""
        await update.message.reply_text(
            "💸 <b>Withdraw</b>\n\n"
            "Withdraw functionality is being refactored.",
            parse_mode='HTML'
        )
    
    async def bridge_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Bridge command - placeholder"""
        await update.message.reply_text(
            "🌉 <b>Bridge</b>\n\n"
            "Bridge functionality is being refactored.",
            parse_mode='HTML'
        )
    
    async def aggressive_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Aggressive command - placeholder"""
        await update.message.reply_text(
            "⚡ <b>Aggressive Trading</b>\n\n"
            "Aggressive trading functionality is being refactored.",
            parse_mode='HTML'
        )
    
    async def transact_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Transact command - placeholder"""
        await update.message.reply_text(
            "💳 <b>Transact</b>\n\n"
            "Transaction functionality is being refactored.",
            parse_mode='HTML'
        )
    
    # Placeholder methods for callback handlers that need to be implemented
    async def _handle_create_wallet_callback(self, query, context):
        """Handle wallet creation callback - placeholder"""
        await query.edit_message_text(
            "🔐 <b>Creating Wallet...</b>\n\n"
            "This functionality is being refactored. Please use <code>/create</code> command for now.",
            parse_mode='HTML'
        )
    
    async def _handle_analyze_callback(self, query, context, symbol):
        """Handle analyze callback - placeholder"""
        await query.edit_message_text(
            f"📊 <b>Analyzing {symbol}...</b>\n\n"
            "This functionality is being refactored. Please use <code>/analyze {symbol}</code> command for now.",
            parse_mode='HTML'
        )
    
    async def _handle_balance_callback(self, query, context):
        """Handle balance callback - placeholder"""
        await query.edit_message_text(
            "💰 <b>Loading Balance...</b>\n\n"
            "This functionality is being refactored. Please use <code>/balance</code> command for now.",
            parse_mode='HTML'
        )
    
    async def _handle_positions_callback(self, query, context):
        """Handle positions callback - placeholder"""
        await query.edit_message_text(
            "📈 <b>Loading Positions...</b>\n\n"
            "This functionality is being refactored. Please use <code>/positions</code> command for now.",
            parse_mode='HTML'
        )
    
    async def _handle_export_callback(self, query, context):
        """Handle export callback - placeholder"""
        await query.edit_message_text(
            "💾 <b>Exporting Wallet...</b>\n\n"
            "This functionality is being refactored. Please use <code>/export</code> command for now.",
            parse_mode='HTML'
        )
    
    async def _handle_portfolio_callback(self, query, context):
        """Handle portfolio callback - placeholder"""
        await query.edit_message_text(
            "📊 <b>Loading Portfolio...</b>\n\n"
            "This functionality is being refactored. Please use <code>/portfolio</code> command for now.",
            parse_mode='HTML'
        )
    
    async def _handle_back_to_main_callback(self, query, context):
        """Handle back to main callback - placeholder"""
        await query.edit_message_text(
            "🏠 <b>Main Menu</b>\n\n"
            "This functionality is being refactored. Please use <code>/start</code> command for now.",
            parse_mode='HTML'
        )
    
    async def _handle_back_to_wallet_callback(self, query, context):
        """Handle back to wallet callback - placeholder"""
        await query.edit_message_text(
            "🔐 <b>Wallet Management</b>\n\n"
            "This functionality is being refactored. Please use <code>/wallet</code> command for now.",
            parse_mode='HTML'
        )
    
    async def _handle_trade_callback(self, query, context, symbol, side):
        """Handle trade callback - placeholder"""
        await query.edit_message_text(
            f"📈 <b>Trading {symbol} {side}</b>\n\n"
            "This functionality is being refactored. Please use <code>/trade</code> command for now.",
            parse_mode='HTML'
        )
    
    async def _handle_wallet_backup(self, query):
        """Handle wallet backup - placeholder"""
        await self.wallet_manager.get_wallet_backup(query)
    
    async def _handle_wallet_deletion(self, query):
        """Handle wallet deletion - placeholder"""
        await query.edit_message_text(
            "⚠️ <b>Delete Wallet</b>\n\n"
            "This functionality is being refactored. Please use <code>/wallet</code> command for now.",
            parse_mode='HTML'
        )
    
    async def _confirm_wallet_deletion(self, query):
        """Confirm wallet deletion - placeholder"""
        await self.wallet_manager.confirm_wallet_deletion(query)
    
    async def _get_privy_wallet_backup(self, user):
        """Get Privy wallet backup - placeholder"""
        return f"""
🔐 <b>Wallet Backup</b>

<b>Wallet Address:</b>
<code>{user.wallet_address}</code>

<b>⚠️ Note:</b> This is a basic wallet backup.
For full backup features, configure Privy integration.

<b>🔐 Security Reminder:</b>
• Keep your wallet information secure
• Never share your private keys
• Use a secure password manager
        """
    
    async def _load_user_from_supabase(self, user_id: int, telegram_user: Any = None):
        """Load user from Supabase"""
        if self.supabase_service:
            try:
                user_data = await self.supabase_service.get_user(user_id)
                if user_data:
                    # Convert Supabase data to UserState
                    user = UserState(
                        telegram_user_id=user_data['telegram_user_id'],
                        username=user_data.get('username'),
                        first_name=user_data.get('first_name'),
                        last_name=user_data.get('last_name'),
                        wallet_address=user_data.get('wallet_address'),
                        private_key_encrypted=user_data.get('private_key_encrypted'),
                        mnemonic_encrypted=user_data.get('mnemonic_encrypted'),
                        privy_user_id=user_data.get('privy_user_id'),
                        session_signer=user_data.get('session_signer'),
                        auto_trading_enabled=user_data.get('auto_trading_enabled', False),
                        risk_per_trade=user_data.get('risk_per_trade', 0.05),
                        max_position_size=user_data.get('max_position_size', 0.20),
                        min_confidence=user_data.get('min_confidence', 70),
                        total_trades=user_data.get('total_trades', 0),
                        total_earnings=user_data.get('total_earnings', 0.0),
                        win_rate=user_data.get('win_rate', 0.0),
                        total_pnl=user_data.get('total_pnl', 0.0),
                        is_active=user_data.get('is_active', True),
                        last_active=user_data.get('last_active'),
                        consecutive_losses=user_data.get('consecutive_losses', 0),
                        last_trade_time=user_data.get('last_trade_time'),
                        daily_trade_count=user_data.get('daily_trade_count', 0),
                        daily_pnl=user_data.get('daily_pnl', 0.0)
                    )
                    self.users[user_id] = user
                    logger.info(f"✅ Loaded user {user_id} from Supabase")
                    return user
                else:
                    logger.info(f"ℹ️ User {user_id} not found in Supabase")
                    return None
            except Exception as e:
                logger.error(f"❌ Failed to load user {user_id} from Supabase: {e}")
                return None
        return None
    
    async def _save_user_to_supabase(self, user: UserState):
        """Save user to Supabase"""
        if self.supabase_service:
            try:
                from supabase_trading_service import UserData
                from datetime import datetime
                
                user_data = UserData(
                    telegram_user_id=user.telegram_user_id,
                    username=user.username,
                    first_name=user.first_name,
                    last_name=user.last_name,
                    wallet_address=user.wallet_address,
                    private_key_encrypted=user.private_key_encrypted,
                    mnemonic_encrypted=user.mnemonic_encrypted,
                    privy_user_id=user.privy_user_id,
                    session_signer=user.session_signer,
                    auto_trading_enabled=user.auto_trading_enabled,
                    risk_per_trade=user.risk_per_trade,
                    max_position_size=user.max_position_size,
                    min_confidence=user.min_confidence,
                    total_trades=user.total_trades,
                    total_earnings=user.total_earnings,
                    win_rate=user.win_rate,
                    total_pnl=user.total_pnl,
                    is_active=user.is_active,
                    last_active=datetime.now()
                )
                
                # Check if user exists
                existing_user = await self.supabase_service.get_user(user.telegram_user_id)
                if existing_user:
                    # Update existing user
                    updates = {
                        'username': user.username,
                        'first_name': user.first_name,
                        'last_name': user.last_name,
                        'wallet_address': user.wallet_address,
                        'private_key_encrypted': user.private_key_encrypted,
                        'mnemonic_encrypted': user.mnemonic_encrypted,
                        'privy_user_id': user.privy_user_id,
                        'session_signer': user.session_signer,
                        'auto_trading_enabled': user.auto_trading_enabled,
                        'risk_per_trade': user.risk_per_trade,
                        'max_position_size': user.max_position_size,
                        'min_confidence': user.min_confidence,
                        'total_trades': user.total_trades,
                        'total_earnings': user.total_earnings,
                        'win_rate': user.win_rate,
                        'total_pnl': user.total_pnl,
                        'is_active': user.is_active,
                        'last_active': datetime.now()
                    }
                    success = await self.supabase_service.update_user(user.telegram_user_id, updates)
                    if success:
                        logger.info(f"✅ Updated user {user.telegram_user_id} in Supabase")
                    else:
                        logger.error(f"❌ Failed to update user {user.telegram_user_id} in Supabase")
                else:
                    # Create new user
                    user_id = await self.supabase_service.create_user(user_data)
                    if user_id:
                        logger.info(f"✅ Created user {user.telegram_user_id} in Supabase")
                    else:
                        logger.error(f"❌ Failed to create user {user.telegram_user_id} in Supabase")
                        
            except Exception as e:
                logger.error(f"❌ Failed to save user {user.telegram_user_id} to Supabase: {e}")
    
    async def _get_user_hyperliquid_client(self, user):
        """Get user Hyperliquid client - placeholder"""
        # This would return a Hyperliquid client for the user
        return None
    
    async def _auto_trading_loop(self):
        """Auto trading loop - placeholder"""
        logger.info("Auto trading loop started (placeholder)")
    
    async def signals_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Signals command - placeholder"""
        await update.message.reply_text(
            "🎯 <b>Trading Signals</b>\n\n"
            "Signals functionality is being refactored.",
            parse_mode='HTML'
        )
    
    def run(self):
        """Run the bot"""
        logger.info("🚀 Starting Hyperliquid Trading Bot...")
        self.application.run_polling()


def main():
    """Main function to run the bot"""
    try:
        bot = HyperliquidTradingBot()
        bot.run()
    except Exception as e:
        logger.error(f"❌ Failed to start bot: {e}")
        raise


if __name__ == "__main__":
    main()
