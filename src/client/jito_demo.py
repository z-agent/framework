from typing import Tuple
import base64
import requests
from solders.transaction import VersionedTransaction

class JitoDemo:
    def __init__(self, wallet, rpc_url):
        self.wallet = wallet
        self.rpc_url = rpc_url

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
            
            print("Sending transaction to RPC...")
            response = requests.post(self.rpc_url, headers=headers, json=payload)
            result = response.json()
            
            if "error" in result:
                error_msg = result.get("error", {}).get("message", str(result["error"]))
                return False, f"Transaction failed: {error_msg}"
                
            return True, result["result"]
            
        except Exception as e:
            return False, f"Transaction error: {str(e)}"

def run_demo():
    """Run the DeFi demo"""
    try:
        # Initialize demo with wallet and RPC URL
        from solders.keypair import Keypair
        import os
        from dotenv import load_dotenv
        
        load_dotenv()
        
        # Get wallet and RPC URL from environment
        wallet = Keypair.from_base58_string(os.getenv("USER_PRIVATE_KEY"))
        rpc_url = os.getenv("RPC_URL")
        
        # Initialize demo
        demo = JitoDemo(wallet, rpc_url)
        
        # Execute trade
        print("\n=== 🌟 Solana DeFi Demo ===\n")
        print(f"🚀 Executing trade on Mainnet")
        print(f"👛 Wallet: {str(wallet.pubkey())}")
        
        # Get quote from Jupiter
        input_mint = "So11111111111111111111111111111111111111112"  # SOL
        output_mint = "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263"  # BONK
        amount = 0.01
        slippage = 50
        
        print("\n1️⃣ Getting quote from Jupiter...")
        quote_url = (
            f"https://quote-api.jup.ag/v6/quote?"
            f"inputMint={input_mint}"
            f"&outputMint={output_mint}"
            f"&amount={int(amount * 1e9)}"
            f"&slippageBps={slippage}"
            f"&onlyDirectRoutes=true"
        )
        
        quote_response = requests.get(quote_url)
        if quote_response.status_code != 200:
            raise Exception(f"Failed to get quote: {quote_response.status_code} - {quote_response.text}")
            
        quote_data = quote_response.json()
        out_amount = int(quote_data["outAmount"]) / 1e5  # BONK has 5 decimals
        
        print(f"💱 Quote received:")
        print(f"   Input: {amount} SOL")
        print(f"   Output: {out_amount:,.2f} tokens")
        print(f"   Price Impact: {quote_data.get('priceImpactPct', 0)}%")
        
        # Get swap transaction
        print("\n2️⃣ Preparing swap transaction...")
        swap_data = {
            "quoteResponse": quote_data,
            "userPublicKey": str(wallet.pubkey()),
            "wrapUnwrapSOL": True,
            "computeUnitPriceMicroLamports": 50000,  # Using compute unit price for priority
            "asLegacyTransaction": True
        }
        
        swap_response = requests.post("https://quote-api.jup.ag/v6/swap", json=swap_data)
        if swap_response.status_code != 200:
            raise Exception(f"Failed to prepare swap: {swap_response.status_code} - {swap_response.text}")
            
        swap_result = swap_response.json()
        if "swapTransaction" not in swap_result:
            raise Exception("No swap transaction returned")
            
        # Sign and send transaction
        print("\n3️⃣ Sending transaction...")
        success, tx_result = demo.send_transaction(swap_result["swapTransaction"])
        
        if not success:
            raise Exception(f"Transaction failed: {tx_result}")
            
        print(f"\n✅ Trade submitted successfully!")
        print(f"Transaction signature: {tx_result}")
        print(f"Expected output: {out_amount:,.2f} tokens")
        print(f"\nView transaction: https://solscan.io/tx/{tx_result}")
        
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        return {
            "status": "error",
            "error": str(e)
        }

if __name__ == "__main__":
    run_demo()