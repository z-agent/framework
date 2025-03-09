import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
import requests
from dotenv import load_dotenv
import json
import re

load_dotenv()

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

class ZARATelegramBot:
    def __init__(self):
        self.base_url = os.getenv("ZAPI_URL", "http://localhost:8000")
        self.z_api_url = os.getenv("Z_API_URL", "https://z-api.vistara.dev/v1")
        self.agent_id = None
        self.token = os.getenv("TELEGRAM_TOKEN")
        self.connected_wallets = {}  # Store connected wallet addresses by user ID
        if not self.token:
            raise ValueError("TELEGRAM_TOKEN environment variable not set")

    async def create_agent(self):
        """Create a ZARA agent with analysis tools"""
        try:
            # Get available tools
            response = requests.get(f"{self.base_url}/tool_search?query=solana", timeout=10)
            response.raise_for_status()
            tools = response.json()
            tool_ids = [tool.get("payload", {}).get("id") for tool in tools]
            
            workflow_request = {
                "name": "ZARA Telegram Bot",
                "description": "Agent for ZARA token analysis and operations",
                "arguments": ["query"],
                "agents": {
                    "zara_expert": {
                        "role": "ZARA Token Expert",
                        "goal": "Analyze and execute ZARA token operations",
                        "backstory": "Expert in ZARA token analysis and Solana operations",
                        "agent_tools": tool_ids
                    }
                },
                "tasks": {
                    "analysis": {
                        "description": "{query}",
                        "expected_output": "Analysis result",
                        "agent": "zara_expert",
                        "context": []
                    }
                }
            }
            
            response = requests.post(
                f"{self.base_url}/save_agent",
                json=workflow_request
            )
            response.raise_for_status()
            self.agent_id = response.json()["agent_id"]
            return True, "✨ Agent initialized successfully!"
        except Exception as e:
            return False, f"❌ Failed to initialize agent: {str(e)}"

    async def execute_query(self, query):
        """Execute a query using the agent"""
        if not self.agent_id:
            success, msg = await self.create_agent()
            if not success:
                return {"error": msg}
        
        try:
            print(f"executing query: {query}")
            # If query is a dictionary, use it directly as the request body
            request_body = {"query": query} if isinstance(query, str) else query
            response = requests.post(
                f"{self.base_url}/agent_call",
                params={"agent_id": self.agent_id},
                json=request_body
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": f"Query failed: {str(e)}"}

    async def analyze_with_z_conscious(self, query: str):
        """Get analysis from Z-Conscious API"""
        try:
            response = requests.post(
                # d0f17ac363aa30bf.5HJMWAGexl8J7-V2IazxbW0MVxE7WiRahEXquxVMDOc X-API-KEY:
                f"{self.z_api_url}/analyze",
                json={"query": query},
                headers={"X-API-KEY": "d0f17ac363aa30bf.5HJMWAGexl8J7-V2IazxbW0MVxE7WiRahEXquxVMDOc"},
                timeout=20
            )
            response.raise_for_status()
            result = response.json()
            result['response'] = result['analysis']
            print(result)
            return result
        except Exception as e:
            return {"error": f"Z-Analysis failed: {str(e)}"}

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Send a message when the command /start is issued."""
        keyboard = [
            [
                InlineKeyboardButton("Analyze", callback_data="analyze"),
                InlineKeyboardButton("Trade", callback_data="trade"),
            ],
            [
                InlineKeyboardButton("Insights", callback_data="insights"),
                InlineKeyboardButton("Network", callback_data="network"),
            ],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "👋 lets get started!\n\n"
            "what would you like to do?\n"
            "Choose an option below:",
            reply_markup=reply_markup
        )

    async def show_trading_menu(self, update: Update):
        """Display the trading menu."""
        keyboard = [
            [
                InlineKeyboardButton("Connect Wallet", callback_data="connect_wallet"),
                InlineKeyboardButton("Check Balance", callback_data="check_balance"),
            ],
            [
                InlineKeyboardButton("Buy ZARA", callback_data="buy"),
                InlineKeyboardButton("Sell ZARA", callback_data="sell"),
            ],
            [
                InlineKeyboardButton("Stake ZARA", callback_data="stake"),
                InlineKeyboardButton("Unstake ZARA", callback_data="unstake"),
            ],
            [InlineKeyboardButton("« Back to Main Menu", callback_data="main_menu")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        return "🏦 ZARA Trading Menu\n\nSelect an operation:", reply_markup

    async def execute_trade(self, operation: str, amount: float = None, token: str = None) -> dict:
        """Execute a real trade using Jupiter."""
        try:
            # Build trade query
            if not amount:
                amount = 0.01  # Default amount in SOL
            
            # Build natural language query
            query = f"Execute trade: {operation} {amount} {token or 'ZARA'} tokens with SOL using 20% slippage"
            
            # Execute the trade through the agent
            trade_result = await self.execute_query({"query": query})
            
            if "error" in trade_result:
                return {"error": trade_result["error"]}
                
            print(f"Trade result: {trade_result}")
            
            # Parse the response which might be a JSON string
            response_data = trade_result.get('response', '')
            if isinstance(response_data, str):
                try:
                    parsed_result = json.loads(response_data)
                except json.JSONDecodeError:
                    return {
                        "success": True,
                        "message": response_data,
                        "transaction_id": "",
                        "input_amount": amount,
                        "output_amount": 0,
                        "price_impact": 0
                    }
            else:
                parsed_result = response_data

            # Extract details from parsed result
            if isinstance(parsed_result, dict):
                details = parsed_result.get('details', {})
                return {
                    "success": True,
                    "message": parsed_result.get('message', 'Trade completed successfully'),
                    "transaction_id": details.get('signature', ''),
                    "input_amount": details.get('input_amount', amount),
                    "output_amount": details.get('output_amount', 0),
                    "price_impact": details.get('price_impact', 0),
                    "token_symbol": details.get('token_symbol', token or 'ZARA')
                }
            else:
                return {
                    "success": True,
                    "message": str(parsed_result),
                    "transaction_id": "",
                    "input_amount": amount,
                    "output_amount": 0,
                    "price_impact": 0
                }
            
        except Exception as e:
            print(f"Error in execute_trade: {e}")
            return {"error": f"Trade failed: {str(e)}"}

    async def button(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle button presses."""
        query = update.callback_query
        await query.answer()

        if query.data == "trading":
            message, reply_markup = await self.show_trading_menu(update)
            await query.edit_message_text(text=message, reply_markup=reply_markup)
            return

        if query.data == "main_menu":
            keyboard = [
                [
                    InlineKeyboardButton("Analyze ZARA", callback_data="analyze"),
                    InlineKeyboardButton("Network Status", callback_data="network"),
                ],
                [
                    InlineKeyboardButton("Get Insights", callback_data="insights"),
                    InlineKeyboardButton("Trading Menu", callback_data="trading"),
                ],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                "Main Menu\nChoose an option below:",
                reply_markup=reply_markup
            )
            return

        if query.data == "connect_wallet":
            user_id = update.effective_user.id
            # Get real wallet connection status from agent
            result = await self.execute_query("Connect wallet and get status")
            if "error" in result:
                await query.edit_message_text(f"❌ Wallet connection failed: {result['error']}")
                return
                
            self.connected_wallets[user_id] = result.get("wallet_address", "")
            await query.edit_message_text(
                f"🔗 Wallet connected\nAddress: {self.connected_wallets[user_id][:6]}...{self.connected_wallets[user_id][-4:]}"
            )
            return

        if query.data in ["buy", "sell", "stake", "unstake"]:
            user_id = update.effective_user.id
            if user_id not in self.connected_wallets:
                await query.edit_message_text("❌ Please connect your wallet first")
                return
                
            await query.edit_message_text(f"💫 Preparing {query.data} transaction...")
            result = await self.execute_trade(query.data)
            
            if "error" in result:
                await query.edit_message_text(f"❌ {result['error']}")
            else:
                keyboard = [[InlineKeyboardButton("« Back to Trading", callback_data="trading")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await query.edit_message_text(
                    text=result["message"],
                    reply_markup=reply_markup
                )
            return

        if query.data == "check_balance":
            user_id = update.effective_user.id
            if user_id not in self.connected_wallets:
                await query.edit_message_text("❌ Please connect your wallet first")
                return
                
            await query.edit_message_text("🔍 Fetching balance...")
            result = await self.execute_query(
                f"Get token balances for wallet {self.connected_wallets[user_id]}"
            )
            
            if "error" in result:
                await query.edit_message_text(f"❌ {result['error']}")
            else:
                balance_text = (
                    "💰 Wallet Balance\n\n"
                    f"ZARA: {result.get('zara_balance', '0')} tokens\n"
                    f"USDC: {result.get('usdc_balance', '0')}\n"
                    f"SOL: {result.get('sol_balance', '0')}\n"
                    f"Staked ZARA: {result.get('staked_balance', '0')} tokens\n"
                    f"Earned Rewards: {result.get('earned_rewards', '0')} ZARA"
                )
                keyboard = [[InlineKeyboardButton("« Back to Trading", callback_data="trading")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await query.edit_message_text(text=balance_text, reply_markup=reply_markup)
            return

        # Handle existing button actions
        if query.data == "analyze":
            await query.edit_message_text("🔍 Analyzing ZARA token...")
            result = await self.execute_query(
                "Analyze ZARA token (73UdJevxaNKXARgkvPHQGKuv8HCZARszuKW2LTL3pump) using TokenFundamentalAnalysis and TokenTechnicalAnalysis tools"
            )
            
            if "error" in result:
                await query.edit_message_text(f"❌ {result['error']}")
            else:
                # Format analysis results
                analysis = result.get('response', {})
                if isinstance(analysis, dict):
                    formatted_analysis = "📊 ZARA Analysis\n\n"
                    
                    if "Price (USDC)" in analysis:
                        formatted_analysis += f"💰 Price: {analysis['Price (USDC)']} USDC\n"
                    if "24h Volume" in analysis:
                        formatted_analysis += f"📈 24h Volume: {analysis['24h Volume']}\n"
                    if "Market Cap" in analysis:
                        formatted_analysis += f"💎 Market Cap: {analysis['Market Cap']}\n"
                    if "Price Change 24h" in analysis:
                        formatted_analysis += f"📊 24h Change: {analysis['Price Change 24h']}\n"
                    if "Network Health" in analysis:
                        formatted_analysis += f"🌐 Network: {analysis['Network Health']}\n"
                        
                    keyboard = [[InlineKeyboardButton("« Back to Menu", callback_data="main_menu")]]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    await query.edit_message_text(text=formatted_analysis, reply_markup=reply_markup)
                else:
                    await query.edit_message_text(f"📊 Analysis Results:\n\n{analysis}")

        elif query.data == "network":
            await query.edit_message_text("🔍 Checking network status...")
            result = await self.execute_query(
                "Get current network performance metrics including TPS, slot times, and validator health"
            )
            if "error" in result:
                await query.edit_message_text(f"❌ {result['error']}")
            else:
                await query.edit_message_text(f"🌐 Network Status:\n\n{result['response']}")

        elif query.data == "insights":
            await query.edit_message_text("🔍 Getting insights...")
            result = await self.analyze_with_z_conscious(
                "Analyze the current state of ZARA token and Solana DeFi ecosystem"
            )
            print(f"getting insights result: {result}\n\n")
            if "error" in result:
                await query.edit_message_text(f"❌ {result['error']}")
            else:
                await query.edit_message_text(f"💡 ZARA Insights:\n\n{result['response'].get('analysis', '')}")

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Send a message when the command /help is issued."""
        help_text = (
            "🤖 ZARA Bot Commands:\n\n"
            "/start - Start interacting with the bot\n"
            "/analyze - Analyze ZARA token\n"
            "/network - Check network status\n"
            "/insights - Get market insights\n"
            "/trade - Open trading menu\n"
            "/help - Show this help message"
        )
        await update.message.reply_text(help_text)

    async def analyze_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle the /analyze command."""
        await update.message.reply_text("🔍 Analyzing ZARA token...")
        result = await self.execute_query(
            "Analyze ZARA token (73UdJevxaNKXARgkvPHQGKuv8HCZARszuKW2LTL3pump) including price, volume, and market metrics"
        )
        print(result)
        if "error" in result:
            await update.message.reply_text(f"❌ {result['error']}")
        else:
            await update.message.reply_text(f"📊 Analysis Results:\n\n{result.get('raw', '')}")

    async def network_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle the /network command."""
        await update.message.reply_text("🔍 Checking network status...")
        result = await self.execute_query(
            "Get current network performance metrics including TPS, slot times, and validator health"
        )
        if "error" in result:
            await update.message.reply_text(f"❌ {result['error']}")
        else:
            await update.message.reply_text(f"🌐 Network Status:\n\n{result.get('raw', '')}")

    async def insights_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle the /insights command."""
        await update.message.reply_text("🔍 Getting insights...")
        result = await self.analyze_with_z_conscious(
            "Analyze the current state of ZARA token and Solana DeFi ecosystem"
        )
        if "error" in result:
            await update.message.reply_text(f"❌ {result['error']}")
        else:
            await update.message.reply_text(f"💡 ZARA Insights:\n\n{result.get('response', '')}")

    async def trade_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle the /trade command."""
        message, reply_markup = await self.show_trading_menu(update)
        await update.message.reply_text(text=message, reply_markup=reply_markup)

    async def handle_trading_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle natural language trading commands."""
        message = update.message.text.lower()
        
        # Extract amount and token
        amount_match = re.search(r'(\d+(?:\.\d+)?)', message)
        amount = float(amount_match.group(1)) if amount_match else None
        
        # Extract token symbol - look for word after amount
        token_match = re.search(r'(?:\d+(?:\.\d+)?)\s+(\w+)', message)
        token = token_match.group(1).upper() if token_match else None
        
        if not amount:
            await update.message.reply_text("❌ Please specify an amount (e.g. 'buy 1000 BONK')")
            return
            
        if not token:
            await update.message.reply_text("❌ Please specify a token (e.g. 'buy 1000 BONK')")
            return

        # Send preparing message
        status_msg = await update.message.reply_text(
            f"🔄 Preparing to trade {amount} {token} tokens..."
        )

        # Execute the trade
        operation = "buy" if any(word in message for word in ['buy', 'get', 'purchase']) else "sell"
        result = await self.execute_trade(operation, amount, token)
        
        if "error" in result:
            await status_msg.edit_text(f"❌ {result['error']}")
        else:
            # Show result with a back to menu button
            keyboard = [[InlineKeyboardButton("🏦 Trading Menu", callback_data="trading")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await status_msg.edit_text(text=result["message"], reply_markup=reply_markup)

def main():
    """Start the bot."""
    bot = ZARATelegramBot()
    application = Application.builder().token(bot.token).build()

    # Command handlers
    application.add_handler(CommandHandler("start", bot.start))
    application.add_handler(CommandHandler("help", bot.help_command))
    application.add_handler(CommandHandler("analyze", bot.analyze_command))
    application.add_handler(CommandHandler("network", bot.network_command))
    application.add_handler(CommandHandler("insights", bot.insights_command))
    application.add_handler(CommandHandler("trade", bot.trade_command))
    
    # Message handler for natural language trading
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.Regex(r'(?i)(buy|sell|stake|unstake|get|purchase|dump|exit|lock|unlock|withdraw).*(zara|token)'),
        bot.handle_trading_message
    ))
    
    # Callback query handler
    application.add_handler(CallbackQueryHandler(bot.button))

    # Start the bot
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main() 