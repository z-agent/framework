import os
import sys
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from telegram.ext import MessageHandler, filters
import asyncio
from datetime import datetime
import requests
from dotenv import load_dotenv
from src.tools.agentipy_tools import execute_jupiter_trade

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

load_dotenv()

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

class ZARABot:
    def __init__(self):
        self.base_url = os.getenv("ZAPI_URL", "http://localhost:8000")
        self.z_api_url = os.getenv("Z_API_URL", "https://z-api.vistara.dev")
        self.agent_id = None

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

    async def execute_query(self, query: str):
        """Execute a query using the agent"""
        if not self.agent_id:
            success, msg = await self.create_agent()
            if not success:
                return {"error": msg}
        
        try:
            response = requests.post(
                f"{self.base_url}/agent_call",
                params={"agent_id": self.agent_id},
                json={"query": query}
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": f"Query failed: {str(e)}"}

    async def analyze_with_z_conscious(self, query: str):
        """Get analysis from Z-Conscious API"""
        try:
            response = requests.post(
                f"{self.z_api_url}/analyze",
                json={"query": query},
                timeout=20
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": f"Z-Analysis failed: {str(e)}"}

zara_bot = ZARABot()

def format_message(text: str) -> str:
    """Format text in a cool style"""
    text = text.replace('-', '\\-').replace('.', '\\.').replace('(', '\\(').replace(')', '\\)')
    return f"```\n╔══════════════════════╗\n║ {text} ║\n╚══════════════════════╝\n```"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send welcome message on `/start`."""
    keyboard = [
        [
            InlineKeyboardButton("📊 Token Analysis", callback_data="analysis"),
            InlineKeyboardButton("🌐 Network Status", callback_data="network")
        ],
        [
            InlineKeyboardButton("🧠 Z-Conscious Insights", callback_data="insights"),
            InlineKeyboardButton("ℹ️ Help", callback_data="help")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_text = format_message("🤖 ZARA Analysis Bot")
    menu_text = (
        "Available Commands:\n\n"
        "/analyze \\- Analyze ZARA token\n"
        "/network \\- Check network status\n"
        "/insights \\- Get Z\\-Conscious insights\n"
        "/help \\- Show help\n"
    )
    
    await update.message.reply_text(
        welcome_text + menu_text,
        reply_markup=reply_markup,
        parse_mode='MarkdownV2'
    )

async def analyze_token(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Analyze ZARA token"""
    message = await update.message.reply_text("🔄 Analyzing ZARA token...")
    
    try:
        result = await zara_bot.execute_query(
            "Analyze ZARA token (73UdJevxaNKXARgkvPHQGKuv8HCZARszuKW2LTL3pump) including price, volume, and market metrics"
        )
        
        if "error" in result:
            await message.edit_text(f"❌ Analysis failed: {result['error']}")
            return
            
        analysis_text = f"""
ZARA TOKEN ANALYSIS
══════════════════════
Time: {datetime.now().strftime('%H:%M:%S')}
{result.get('response', 'No data available')}
══════════════════════
Updated: Just Now 🔄
"""
        await message.edit_text(format_message(analysis_text), parse_mode='MarkdownV2')
    except Exception as e:
        await message.edit_text(f"❌ Error: {str(e)}")

async def network_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Get network status"""
    message = await update.message.reply_text("🔄 Checking network status...")
    
    try:
        result = await zara_bot.execute_query(
            "Get current network performance metrics including TPS, slot times, and validator health"
        )
        
        if "error" in result:
            await message.edit_text(f"❌ Status check failed: {result['error']}")
            return
            
        status_text = f"""
NETWORK STATUS
══════════════════════
Time: {datetime.now().strftime('%H:%M:%S')}
{result.get('response', 'No data available')}
══════════════════════
Updated: Just Now 🔄
"""
        await message.edit_text(format_message(status_text), parse_mode='MarkdownV2')
    except Exception as e:
        await message.edit_text(f"❌ Error: {str(e)}")

async def get_insights(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Get Z-Conscious insights"""
    message = await update.message.reply_text("🧠 Getting Z-Conscious insights...")
    
    try:
        result = await zara_bot.analyze_with_z_conscious(
            "Analyze the current state of ZARA token and Solana DeFi ecosystem"
        )
        
        if "error" in result:
            await message.edit_text(f"❌ Analysis failed: {result['error']}")
            return
            
        insights_text = f"""
Z-CONSCIOUS INSIGHTS
══════════════════════
Time: {datetime.now().strftime('%H:%M:%S')}
{result.get('response', 'No insights available')}
══════════════════════
Updated: Just Now 🔄
"""
        await message.edit_text(format_message(insights_text), parse_mode='MarkdownV2')
    except Exception as e:
        await message.edit_text(f"❌ Error: {str(e)}")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle button presses"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "analysis":
        await analyze_token(update, context)
    elif query.data == "network":
        await network_status(update, context)
    elif query.data == "insights":
        await get_insights(update, context)
    elif query.data == "help":
        help_text = format_message(
            "ZARA Bot Help\n"
            "Use commands or buttons to:\n"
            "- Analyze ZARA token\n"
            "- Check network status\n"
            "- Get AI insights"
        )
        await query.message.reply_text(help_text, parse_mode='MarkdownV2')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send help message."""
    await update.message.reply_text(
        "🤖 ZARA Bot Commands:\n\n"
        "/trade <amount> - Buy ZARA tokens with SOL\n"
        "Example: /trade 0.1 (buys ZARA with 0.1 SOL)"
    )

async def trade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Execute ZARA trade."""
    try:
        # Parse amount from command
        if not context.args:
            await update.message.reply_text("❌ Please specify amount: /trade <amount>")
            return
            
        amount = float(context.args[0])
        if amount <= 0 or amount > 0.1:
            await update.message.reply_text("❌ Amount must be between 0 and 0.1 SOL")
            return
            
        # Send processing message
        message = await update.message.reply_text(f"🔄 Processing trade: {amount} SOL → ZARA...")
        
        # Execute trade
        result = await execute_jupiter_trade(
            output_mint="73UdJevxaNKXARgkvPHQGKuv8HCZARszuKW2LTL3pump",
            amount=amount,
            slippage_bps=2000  # 20% slippage
        )
        
        # Format success message
        success_msg = (
            f"✅ Trade Successful!\n\n"
            f"💰 Swapped: {amount} SOL → {result['output_amount']:.6f} ZARA\n"
            f"📊 Price Impact: {result['price_impact']:.2f}%\n\n"
            f"🔗 View transaction:\n"
            f"https://solscan.io/tx/{result['signature']}"
        )
        
        await message.edit_text(success_msg)
        
    except ValueError:
        await update.message.reply_text("❌ Invalid amount format. Example: /trade 0.1")
    except Exception as e:
        await update.message.reply_text(f"❌ Trade failed: {str(e)}")

def main() -> None:
    """Start the bot"""
    # Create application and add handlers
    application = Application.builder().token(os.getenv("TELEGRAM_BOT_TOKEN")).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("analyze", analyze_token))
    application.add_handler(CommandHandler("network", network_status))
    application.add_handler(CommandHandler("insights", get_insights))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("trade", trade))
    
    # Start the bot
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main() 