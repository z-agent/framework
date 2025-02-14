import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from telegram.ext import MessageHandler, filters
import asyncio
from datetime import datetime
import json
import requests
from dotenv import load_dotenv

load_dotenv()

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

class RetroSolanaBot:
    def __init__(self):
        self.base_url = "http://localhost:8000"
        self.agent_id = None
        self.jito_demo = None

    def init_jito(self):
        """Initialize Jito demo with wallet and RPC URL"""
        if not self.jito_demo:
            from solders.keypair import Keypair
            wallet = Keypair.from_base58_string(os.getenv("USER_PRIVATE_KEY"))
            rpc_url = os.getenv("RPC_URL")
            from src.client.jito_demo import JitoDemo
            self.jito_demo = JitoDemo(wallet, rpc_url)
        return self.jito_demo

    async def create_agent(self):
        """Create a Solana agent with all necessary tools"""
        workflow_request = {
            "name": "Solana RetroBot Agent",
            "description": "Agent for executing various Solana operations",
            "arguments": ["query"],
            "agents": {
                "alpha_trader": {
                    "role": "Quantitative Trading Expert",
                    "goal": "Execute advanced trading strategies with optimal timing",
                    "backstory": "Expert quant trader specializing in MEV and arbitrage",
                    "agent_tools": [
                        "Solana Trade",
                        "Solana Fetch Price",
                        "Solana Get Tps",
                        "Solana Transfer"
                    ]
                }
            },
            "tasks": {
                "analysis": {
                    "description": "{query}",
                    "expected_output": "Operation execution result",
                    "agent": "alpha_trader"
                }
            }
        }
        
        response = requests.post(
            f"{self.base_url}/save_agent",
            json=workflow_request
        )
        response.raise_for_status()
        self.agent_id = response.json()["agent_id"]
        return self.agent_id

    async def execute_query(self, query: str):
        """Execute a query using the agent"""
        if not self.agent_id:
            await self.create_agent()
        
        response = requests.post(
            f"{self.base_url}/agent_call",
            params={"agent_id": self.agent_id},
            json={"query": query}
        )
        response.raise_for_status()
        return response.json()

    async def execute_jito_trade(self, amount: float, token: str = "BONK"):
        """Execute a trade using Jito"""
        try:
            demo = self.init_jito()
            
            # Token mapping
            token_map = {
                "BONK": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
                "JTO": "jtojtomepa8beP8AuQc6eXt5FriJwfkmzuLzWWUdSbr",
                "SAMO": "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU"
            }
            
            # Get token address
            if len(token) < 32:  # If token symbol provided
                if token.upper() not in token_map:
                    return "❌ Invalid token. Supported: BONK, JTO, SAMO"
                token_address = token_map[token.upper()]
            else:  # If full address provided
                token_address = token
            
            # Get quote
            input_mint = "So11111111111111111111111111111111111111112"  # SOL
            quote_url = (
                f"https://quote-api.jup.ag/v6/quote?"
                f"inputMint={input_mint}"
                f"&outputMint={token_address}"
                f"&amount={int(amount * 1e9)}"
                f"&slippageBps=50"
                f"&onlyDirectRoutes=true"
            )
            
            quote_response = requests.get(quote_url)
            if quote_response.status_code != 200:
                return "❌ Failed to get quote"
                
            quote_data = quote_response.json()
            decimals = 5 if token.upper() == "BONK" else 6
            out_amount = int(quote_data["outAmount"]) / (10 ** decimals)
            
            # Get swap transaction
            swap_data = {
                "quoteResponse": quote_data,
                "userPublicKey": str(demo.wallet.pubkey()),
                "wrapUnwrapSOL": True,
                "computeUnitPriceMicroLamports": 50000,
                "asLegacyTransaction": True
            }
            
            swap_response = requests.post("https://quote-api.jup.ag/v6/swap", json=swap_data)
            if swap_response.status_code != 200:
                return "❌ Failed to prepare swap"
                
            swap_result = swap_response.json()
            if "swapTransaction" not in swap_result:
                return "❌ No swap transaction returned"
                
            # Sign and send transaction
            success, tx_result = demo.send_transaction(swap_result["swapTransaction"])
            
            if not success:
                return f"❌ Transaction failed: {tx_result}"
                
            return {
                "status": "success",
                "signature": tx_result,
                "input": f"{amount} SOL",
                "output": f"{out_amount:,.2f} {token.upper()}",
                "price_impact": f"{quote_data.get('priceImpactPct', 0)}%"
            }
            
        except Exception as e:
            return f"❌ Error: {str(e)}"

solana_bot = RetroSolanaBot()

def format_retro(text: str) -> str:
    """Format text in retro style"""
    # Escape special characters for MarkdownV2
    text = text.replace('-', '\\-').replace('.', '\\.').replace('(', '\\(').replace(')', '\\)')
    return f"```\n╔══════════════════════╗\n║ {text} ║\n╚══════════════════════╝\n```"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send message on `/startztrade`."""
    keyboard = [
        [
            InlineKeyboardButton("🌐 Network Status", callback_data="network"),
            InlineKeyboardButton("💰 Token Prices", callback_data="prices")
        ],
        [
            InlineKeyboardButton("📊 MEV Analysis", callback_data="mev"),
            InlineKeyboardButton("⚡ Jito Trading", callback_data="jito")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_text = format_retro("🤖 RETRO SOLANA BOT v1\\.0")
    menu_text = (
        "🎮 Available Commands:\n\n"
        "/network \\- Check Solana Network Status\n"
        "/price \\<token\\> \\- Check Token Price\n"
        "/mev \\<token\\> \\- Analyze MEV Opportunities\n"
        "/jito \\<amount\\> \\<token\\> \\- Execute Jito Trade\n\n"
        "Example tokens:\n"
        "\\- BONK: DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263\n"
        "\\- JTO: jtojtomepa8beP8AuQc6eXt5FriJwfkmzuLzWWUdSbr\n"
        "\\- SAMO: 7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU"
    )
    
    await update.message.reply_text(
        welcome_text + menu_text,
        reply_markup=reply_markup,
        parse_mode='MarkdownV2'
    )

async def network_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Get Solana network status"""
    # Handle both direct commands and callback queries
    if update.callback_query:
        message = await update.callback_query.message.reply_text("🔄 Analyzing network...")
    else:
        message = await update.message.reply_text("🔄 Analyzing network...")
        
    try:
        result = await solana_bot.execute_query("Get current TPS and assess network conditions")
        
        # Extract TPS from result
        raw_text = str(result.get('raw', ''))
        try:
            tps = float([x for x in raw_text.split() if 'TPS' in x or 'tps' in x][0].split()[0])
        except (IndexError, ValueError):
            tps = float(str(result).split('is')[1].split('.')[0].strip())
        
        # Determine network load status
        if tps < 100:
            status = "🟢 OPTIMAL"
            load = "LOW LOAD \\- Perfect for Trading"
        elif tps < 1000:
            status = "🟡 BUSY"
            load = "MEDIUM LOAD \\- Trade with Caution"
        else:
            status = "🔴 CONGESTED"
            load = "HIGH LOAD \\- High Slippage Risk"
            
        # Get network type from env
        network = "DEVNET" if "devnet" in os.getenv("SOLANA_RPC_URL", "").lower() else "MAINNET"
        
        status_text = f"""
SOLANA NETWORK RADAR
══════════════════════
Time: {datetime.now().strftime('%H:%M:%S')}
Network: {network}
TPS: {tps:.2f}
Status: {status}
Load: {load}
══════════════════════
Updated: Just Now 🔄
"""
        await message.edit_text(format_retro(status_text), parse_mode='MarkdownV2')
    except Exception as e:
        error_text = f"""
ERROR REPORT
══════════════
Type: Network Analysis
Status: Failed
Reason: {str(e)[:50]}
Action: Please try again
══════════════
"""
        await message.edit_text(format_retro(error_text), parse_mode='MarkdownV2')

async def check_price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Check token price"""
    if not context.args:
        help_text = """
TOKEN PRICE CHECK
═══════════════
Usage: /price <token>

Popular Tokens:
• BONK: DezXAZ...B263
• JTO:  jtoj...dSbr
• SAMO: 7xKX...AsU
═══════════════
"""
        await update.message.reply_text(format_retro(help_text), parse_mode='MarkdownV2')
        return
        
    token = context.args[0]
    message = await update.message.reply_text("💰 Fetching price...")
    
    try:
        # First get network status
        network_result = await solana_bot.execute_query("Get current TPS")
        tps = 0
        try:
            raw_text = str(network_result)
            tps = float([x for x in raw_text.split() if x.replace('.', '').isdigit()][0])
        except:
            tps = 0
            
        # Then get price
        result = await solana_bot.execute_query(f"Get detailed price analysis for token {token}")
        
        # Try to extract price and other details with safer parsing
        raw_text = str(result)
        price = "Analyzing..."
        volume = "Calculating..."
        
        # Try different patterns to extract price
        try:
            if 'price' in raw_text.lower():
                price_text = [x for x in raw_text.split() if '$' in x or 'SOL' in x]
                if price_text:
                    price = price_text[0]
            if 'volume' in raw_text.lower():
                volume = raw_text.split('volume')[1].split('.')[0].strip()
        except:
            pass
            
        price_text = f"""
TOKEN ANALYSIS v2.0
══════════════════
Token: {token[:4]}...{token[-4:]}
Price: {price}
Network: {'DEVNET' if 'devnet' in os.getenv('SOLANA_RPC_URL', '').lower() else 'MAINNET'}
TPS: {tps:.2f}
Time: {datetime.now().strftime('%H:%M:%S')}
══════════════════
Status: Real-time 🔄
"""
        await message.edit_text(format_retro(price_text), parse_mode='MarkdownV2')
    except Exception as e:
        error_text = f"""
ERROR REPORT
══════════════
Type: Price Check
Token: {token[:4]}...{token[-4:]}
Status: Failed
Reason: {str(e)[:50]}
Action: Please try again
══════════════
"""
        await message.edit_text(format_retro(error_text), parse_mode='MarkdownV2')

async def analyze_mev(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Analyze MEV opportunities"""
    if not context.args:
        help_text = """
MEV SCANNER v1.0
═══════════════
Usage: /mev <token>

Supported DEXes:
• Jupiter
• Orca
• Raydium

Example: /mev DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263
═══════════════
"""
        await update.message.reply_text(format_retro(help_text), parse_mode='MarkdownV2')
        return
        
    token = context.args[0]
    message = await update.message.reply_text("🔍 Initializing MEV Scanner...")
    
    try:
        # First get network status
        network_result = await solana_bot.execute_query("Get current TPS")
        tps = float(str(network_result).split('is')[1].split('.')[0].strip())
        
        # Then analyze MEV
        result = await solana_bot.execute_query(f"""
        Quick arbitrage check for {token}:
        1. Get current price on Jupiter, Orca, Raydium
        2. Check liquidity depth
        3. Calculate potential arbitrage (accounting for 0.3% fees)
        4. Factor in TPS of {tps}
        """)
        
        # Extract relevant information
        raw_text = str(result)
        
        mev_text = f"""
MEV OPPORTUNITY SCAN
══════════════════
Token: {token[:4]}...{token[-4:]}
Network: {'DEVNET' if 'devnet' in os.getenv('SOLANA_RPC_URL', '').lower() else 'MAINNET'}
TPS: {tps:.2f}

Analysis:
{raw_text.split('Analysis:')[1].split('.')[0].strip() if 'Analysis:' in raw_text else 'Scanning DEXes...'}

Network Status: {'✅ Good for Trading' if tps < 100 else '⚠️ Proceed with Caution'}
══════════════════
Last Update: {datetime.now().strftime('%H:%M:%S')} 🔄
"""
        await message.edit_text(format_retro(mev_text), parse_mode='MarkdownV2')
    except Exception as e:
        error_text = f"""
ERROR REPORT
══════════════
Type: MEV Analysis
Token: {token[:4]}...{token[-4:]}
Status: Failed
Reason: {str(e)[:50]}
Action: Please try again
══════════════
"""
        await message.edit_text(format_retro(error_text), parse_mode='MarkdownV2')

async def jito_trade(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Execute a Jito trade with safety checks"""
    if len(context.args) < 2:
        help_text = """
JITO TRADE EXECUTOR v1.0
═══════════════════════
Usage: /jito <amount> <token>

Safety Limits:
• Max Trade: 0.1 SOL
• Slippage: 50 bps
• Priority Fee: Auto-adjust

Supported Tokens:
• BONK
• JTO
• SAMO
(or use full address)

Example: /jito 0.01 BONK
═══════════════════════
"""
        await update.message.reply_text(format_retro(help_text), parse_mode='MarkdownV2')
        return
        
    try:
        amount = float(context.args[0])
        token = context.args[1]
        
        # Safety check
        if amount > 0.1:
            safety_text = """
SAFETY ALERT ⚠️
══════════════
Trade Amount Too High
Max Allowed: 0.1 SOL
Action: Reduce Amount
══════════════
"""
            await update.message.reply_text(format_retro(safety_text), parse_mode='MarkdownV2')
            return
            
        message = await update.message.reply_text("🔄 Initializing Jito Trade...")
        
        # First check network conditions
        network_result = await solana_bot.execute_query("Get current TPS")
        tps = 0
        try:
            raw_text = str(network_result)
            tps = float([x for x in raw_text.split() if x.replace('.', '').isdigit()][0])
        except:
            tps = 0
        
        if tps > 1000:
            warning_text = f"""
NETWORK ALERT ⚠️
══════════════
High TPS Detected: {tps:.2f}
Risk: High Slippage
Action: Wait for Better Conditions
══════════════
"""
            await message.edit_text(format_retro(warning_text), parse_mode='MarkdownV2')
            return
            
        # Execute trade
        result = await solana_bot.execute_jito_trade(amount, token)
        
        if isinstance(result, str):  # Error message
            error_text = f"""
TRADE ERROR
══════════════
Status: Failed
Reason: {result}
Action: Please try again
══════════════
"""
            await message.edit_text(format_retro(error_text), parse_mode='MarkdownV2')
        else:  # Success
            success_text = f"""
JITO TRADE EXECUTED
══════════════════
Status: ✅ Success
Input: {result['input']}
Output: {result['output']}
Impact: {result['price_impact']}
Network: {'DEVNET' if 'devnet' in os.getenv('SOLANA_RPC_URL', '').lower() else 'MAINNET'}
TPS: {tps:.2f}

View Transaction:
https://solscan.io/tx/{result['signature']}
══════════════════
Time: {datetime.now().strftime('%H:%M:%S')} 🔄
"""
            await message.edit_text(format_retro(success_text), parse_mode='MarkdownV2')
            
    except ValueError:
        error_text = """
ERROR REPORT
══════════════
Type: Trade Setup
Status: Failed
Reason: Invalid Amount
Action: Use Number (e.g., 0.01)
══════════════
"""
        await update.message.reply_text(format_retro(error_text), parse_mode='MarkdownV2')
    except Exception as e:
        error_text = f"""
ERROR REPORT
══════════════
Type: Trade Execution
Status: Failed
Reason: {str(e)[:50]}
Action: Please try again
══════════════
"""
        await message.edit_text(format_retro(error_text), parse_mode='MarkdownV2')

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle button presses."""
    query = update.callback_query
    await query.answer()

    if query.data == "network":
        await network_status(update, context)
    elif query.data == "prices":
        await query.message.reply_text(
            "Please send a token address to check its price\\.\n"
            "Example: DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
            parse_mode='MarkdownV2'
        )
    elif query.data == "mev":
        await query.message.reply_text(
            "Please send a token address to analyze MEV opportunities\\.\n"
            "Example: DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
            parse_mode='MarkdownV2'
        )
    elif query.data == "jito":
        await query.message.reply_text(
            "Please use format: /jito \\<amount\\> \\<token\\>\n"
            "Example: /jito 0\\.01 BONK\n"
            "Supported tokens: BONK, JTO, SAMO",
            parse_mode='MarkdownV2'
        )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle non-command messages."""
    text = update.message.text.lower()
    
    if len(text) >= 32:  # Likely a token address
        await check_price(update, context)
    else:
        await update.message.reply_text(
            "Please use one of the available commands:\n"
            "/network \\- Check network status\n"
            "/price \\<token\\> \\- Check token price\n"
            "/mev \\<token\\> \\- Analyze MEV\n"
            "/jito \\<amount\\> \\<token\\> \\- Execute trade",
            parse_mode='MarkdownV2'
        )

def main() -> None:
    """Start the bot."""
    # Create the Application
    application = Application.builder().token(os.environ["TELEGRAM_BOT_TOKEN"]).build()

    # Add handlers
    application.add_handler(CommandHandler("startztrade", start))
    application.add_handler(CommandHandler("network", network_status))
    application.add_handler(CommandHandler("price", check_price))
    application.add_handler(CommandHandler("mev", analyze_mev))
    application.add_handler(CommandHandler("jito", jito_trade))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Run the bot
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main() 