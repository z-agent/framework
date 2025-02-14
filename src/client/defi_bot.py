import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
from typing import Dict, Any
import asyncio
from datetime import datetime, timedelta
import json
import requests

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Global variables
PRICE_ALERTS: Dict[str, Dict[str, float]] = {}  # user_id -> {token -> price}
API_BASE_URL = "http://localhost:8000"

class SolanaAnalyzer:
    def __init__(self):
        self.agent_id = None

    async def create_agent(self):
        """Create a Solana analysis agent"""
        response = requests.post(
            f"{API_BASE_URL}/save_agent",
            json={
                "name": "Solana Analysis Agent",
                "description": "Agent for analyzing Solana tokens",
                "arguments": ["query"],
                "agents": {
                    "solana_agent": {
                        "role": "Solana Token Analyst",
                        "goal": "Analyze Solana tokens using various tools",
                        "backstory": "A specialized token analyst",
                        "agent_tools": [
                            "TokenFundamentalAnalysis",
                            "TokenTechnicalAnalysis",
                            "TokenInfoTool"
                        ]
                    }
                },
                "tasks": {
                    "analysis_task": {
                        "description": "{query}",
                        "expected_output": "Analysis result",
                        "agent": "solana_agent"
                    }
                }
            }
        )
        response.raise_for_status()
        self.agent_id = response.json()["agent_id"]
        return self.agent_id

    async def get_token_info(self, token_address: str) -> Dict[str, Any]:
        """Get comprehensive token information"""
        if not self.agent_id:
            await self.create_agent()
        
        response = requests.get(
            f"{API_BASE_URL}/agent_call",
            params={"agent_id": self.agent_id},
            json={"query": f"Analyze token {token_address} using fundamental and technical analysis"}
        )
        response.raise_for_status()
        return response.json()

solana = SolanaAnalyzer()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send message on `/start`."""
    keyboard = [
        [
            InlineKeyboardButton("📊 Token Analysis", callback_data="token_analysis"),
            InlineKeyboardButton("⚡ Set Price Alert", callback_data="set_alert")
        ],
        [
            InlineKeyboardButton("📈 Technical Analysis", callback_data="technical"),
            InlineKeyboardButton("📋 Fundamental Analysis", callback_data="fundamental")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🤖 Welcome to SolanaDefAI Bot!\n\n"
        "I can help you with:\n"
        "- Comprehensive token analysis\n"
        "- Technical analysis\n"
        "- Fundamental analysis\n"
        "- Price alerts\n\n"
        "Choose an option:",
        reply_markup=reply_markup
    )

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle button presses."""
    query = update.callback_query
    await query.answer()

    if query.data == "token_analysis":
        await query.message.reply_text(
            "Please send me the token address you want to analyze.\n"
            "Example: EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v (USDC)"
        )
    elif query.data in ["technical", "fundamental"]:
        await query.message.reply_text(
            f"Please send me the token address for {query.data} analysis.\n"
            f"Format: {query.data} <token_address>"
        )
    elif query.data == "set_alert":
        await query.message.reply_text(
            "To set a price alert, send me a message in this format:\n"
            "alert <token_address> <price>\n\n"
            "Example: alert EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v 1.0"
        )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming messages."""
    text = update.message.text.lower()
    
    if text.startswith("alert "):
        try:
            _, token, price = text.split()
            price = float(price)
            user_id = str(update.effective_user.id)
            
            if user_id not in PRICE_ALERTS:
                PRICE_ALERTS[user_id] = {}
            
            PRICE_ALERTS[user_id][token] = price
            
            # Get current price for reference
            token_info = await solana.get_token_info(token)
            current_price = token_info.get("Price (USDC)", "N/A")
            
            await update.message.reply_text(
                f"✅ Alert set!\n"
                f"Current price: ${current_price}\n"
                f"Alert price: ${price:.2f}"
            )
        except Exception as e:
            await update.message.reply_text(
                "❌ Invalid format. Please use:\n"
                "alert <token_address> <price>"
            )
    
    elif text.startswith(("technical ", "fundamental ")):
        try:
            analysis_type, token = text.split()
            result = await solana.get_token_info(token)
            
            if analysis_type == "technical":
                relevant_info = {k: v for k, v in result.items() if "change" in k.lower() or "volume" in k.lower()}
            else:
                relevant_info = {k: v for k, v in result.items() if "supply" in k.lower() or "cap" in k.lower()}
            
            message = f"📊 {analysis_type.title()} Analysis:\n\n"
            for key, value in relevant_info.items():
                message += f"{key}: {value}\n"
            
            await update.message.reply_text(message)
        except Exception as e:
            await update.message.reply_text(f"Error getting analysis: {str(e)}")
    
    elif len(text) >= 32:  # Assuming it's a token address
        try:
            result = await solana.get_token_info(text)
            message = "📊 Token Analysis:\n\n"
            for key, value in result.items():
                message += f"{key}: {value}\n"
            await update.message.reply_text(message)
        except Exception as e:
            await update.message.reply_text(f"Error getting token info: {str(e)}")

async def check_price_alerts() -> None:
    """Background task to check price alerts."""
    while True:
        for user_id, alerts in PRICE_ALERTS.items():
            for token, target_price in alerts.items():
                try:
                    token_info = await solana.get_token_info(token)
                    current_price = float(token_info.get("Price (USDC)", 0))
                    if current_price >= target_price:
                        print(f"Alert for user {user_id}: {token} reached ${current_price}")
                        del PRICE_ALERTS[user_id][token]
                except Exception as e:
                    print(f"Error checking price alert: {str(e)}")
        
        await asyncio.sleep(60)  # Check every minute

def main() -> None:
    """Start the bot."""
    # Create the Application
    application = Application.builder().token(os.environ["TELEGRAM_BOT_TOKEN"]).build()

    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Start the price alert checker in the background
    asyncio.create_task(check_price_alerts())

    # Run the bot
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main() 