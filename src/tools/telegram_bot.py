import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv
import asyncio
from .agentipy_tools import execute_jupiter_trade
from solders.keypair import Keypair
from solders.transaction import VersionedTransaction
import base64
import requests
from typing import Tuple

load_dotenv()

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send welcome message when /start is issued."""
    await update.message.reply_text(
        "👋 Hi! I'm ZARA bot. Just tell me to buy ZARA tokens and I'll help you trade!"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming messages."""
    text = update.message.text.lower()
    
    if "buy" in text and "zara" in text:
        try:
            # Fixed amount for demo
            amount = 0.01  # 0.01 SOL
            message = await update.message.reply_text(f"🔄 Buying ZARA tokens with {amount} SOL...")
            
            # Initialize trade
            private_key = os.getenv("USER_PRIVATE_KEY")
            wallet = Keypair.from_base58_string(private_key)
            rpc_url = os.getenv("HELIUS_RPC_URL")
            
            # Execute trade using Jito code
            demo = JitoDemo(wallet, rpc_url)
            success, result = demo.execute_trade(amount)
            
            if not success:
                raise Exception(result)
                
            success_msg = (
                f"✅ Trade Successful!\n\n"
                f"💰 Swapped: {amount} SOL → {result['output_amount']:.6f} ZARA\n"
                f"📊 Price Impact: {result['price_impact']}%\n\n"
                f"🔗 View transaction:\n"
                f"https://solscan.io/tx/{result['signature']}"
            )
            
            await message.edit_text(success_msg)
            
        except Exception as e:
            await update.message.reply_text(f"❌ Trade failed: {str(e)}")

class JitoDemo:
    def __init__(self, wallet: Keypair, rpc_url: str):
        self.wallet = wallet
        self.rpc_url = rpc_url
        self.jup_api = "https://quote-api.jup.ag/v6"
        self.zara_mint = "73UdJevxaNKXARgkvPHQGKuv8HCZARszuKW2LTL3pump"
        self.sol_mint = "So11111111111111111111111111111111111111112"

    def send_transaction(self, transaction: str) -> Tuple[bool, str]:
        """Send transaction directly to RPC"""
        try:
            # Decode and sign transaction
            tx_bytes = base64.b64decode(transaction)
            tx = VersionedTransaction.from_bytes(tx_bytes)
            
            # Get message bytes for signing
            message_bytes = bytes(tx.message)
            
            # Sign message with keypair
            signature = self.wallet.sign_message(message_bytes)
            
            # Set the signature in the transaction
            tx.signatures = [signature]
            
            # Serialize and encode
            signed_tx = base64.b64encode(bytes(tx)).decode('utf-8')

            headers = {"Content-Type": "application/json"}
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "sendTransaction",
                "params": [
                    signed_tx,
                    {
                        "encoding": "base64",
                        "skipPreflight": True,
                        "maxRetries": 3,
                        "preflightCommitment": "confirmed"
                    }
                ]
            }
            
            response = requests.post(self.rpc_url, headers=headers, json=payload)
            result = response.json()
            
            if "error" in result:
                error_msg = result.get("error", {}).get("message", str(result["error"]))
                return False, f"Transaction failed: {error_msg}"
                
            return True, result["result"]
            
        except Exception as e:
            return False, f"Transaction error: {str(e)}"

    def execute_trade(self, amount_sol: float = 0.01) -> Tuple[bool, dict]:
        """Execute a ZARA trade with the given SOL amount"""
        try:
            # Get quote
            quote_url = (
                f"{self.jup_api}/quote?"
                f"inputMint={self.sol_mint}"
                f"&outputMint={self.zara_mint}"
                f"&amount={int(amount_sol * 1e9)}"
                f"&slippageBps=2000"
            )
            
            quote_response = requests.get(quote_url)
            if quote_response.status_code != 200:
                raise Exception(f"Failed to get quote: {quote_response.status_code}")
                
            quote_data = quote_response.json()
            out_amount = int(quote_data["outAmount"]) / 1e6  # 6 decimals for ZARA
            
            # Get swap transaction
            swap_data = {
                "route": quote_data,
                "userPublicKey": str(self.wallet.pubkey()),
                "wrapUnwrapSOL": True,
                "computeUnitPriceMicroLamports": "5000000000",  # 5000 lamports priority fee
                "asLegacyTransaction": False,
                "useTokenLedger": False,
                "destinationTokenAccount": None
            }
            
            swap_response = requests.post(
                f"{self.jup_api}/swap",
                headers={"Content-Type": "application/json"},
                json=swap_data
            )
            
            if swap_response.status_code != 200:
                raise Exception(f"Failed to prepare swap: {swap_response.status_code}")
                
            swap_result = swap_response.json()
            if "swapTransaction" not in swap_result:
                raise Exception("No swap transaction returned")
                
            # Sign and send transaction
            success, signature = self.send_transaction(swap_result["swapTransaction"])
            print(f"signature: {signature}")
            if not success:
                raise Exception(f"Failed to send transaction: {signature}")
                
            return True, {
                "signature": signature,
                "output_amount": out_amount,
                "price_impact": quote_data.get("priceImpactPct", 0)
            }
            
        except Exception as e:
            return False, str(e)

def main():
    """Start the bot."""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    print(f"token: {token}")
    if not token:
        print("❌ TELEGRAM_BOT_TOKEN not set in .env")
        return
        
    # Create application and add handlers
    application = Application.builder().token(token).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🤖 ZARA Bot started! Send 'buy zara tokens' to trade")
    
    # Start the bot
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main() 