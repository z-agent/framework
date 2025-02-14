import os
import json
import time
from dotenv import load_dotenv
from solders.keypair import Keypair
import requests

load_dotenv()

class DefiDemo:
    def __init__(self):
        self.rpc_url = os.getenv("SOLANA_RPC_URL")
        self.network = "Mainnet" if "mainnet" in self.rpc_url.lower() else "Devnet"
        self.wallet = Keypair.from_base58_string(os.getenv("SOLANA_PRIVATE_KEY"))
        
        # Popular tokens for demo
        self.tokens = {
            "BONK": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
            "USDC": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
            "JTO": "jtojtomepa8beP8AuQc6eXt5FriJwfkmzuLzWWUdSbr"
        }
        
    def get_network_status(self):
        """Get current network TPS and status"""
        headers = {"Content-Type": "application/json"}
        if "?" in self.rpc_url:
            api_key = self.rpc_url.split("?")[1].split("=")[1]
            headers["Authorization"] = f"Bearer {api_key}"
            
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getRecentPerformanceSamples",
            "params": [1]
        }
        
        response = requests.post(self.rpc_url.split("?")[0], headers=headers, json=payload)
        result = response.json()
        
        if "result" in result:
            sample = result["result"][0]
            tps = sample["numTransactions"] / sample["samplePeriodSecs"]
            return f"✅ Network Status: {tps:.0f} TPS"
        return "❌ Network Status: Error"
        
    def get_token_price(self, token_name: str):
        """Get token price from Jupiter"""
        token_address = self.tokens[token_name]
        url = (
            f"https://quote-api.jup.ag/v6/quote?"
            f"inputMint=So11111111111111111111111111111111111111112"  # SOL
            f"&outputMint={token_address}"
            f"&amount=1000000000"  # 1 SOL
            f"&slippageBps=50"
        )
        
        # Get USDC/SOL price for USD conversion
        usdc_url = (
            f"https://quote-api.jup.ag/v6/quote?"
            f"inputMint=So11111111111111111111111111111111111111112"  # SOL
            f"&outputMint={self.tokens['USDC']}"
            f"&amount=1000000000"  # 1 SOL
            f"&slippageBps=50"
        )
        
        try:
            # Get token price in SOL
            response = requests.get(url)
            if response.status_code != 200:
                return f"❌ {token_name} Price: Error"
                
            data = response.json()
            out_amount = int(data["outAmount"])
            decimals = 5 if token_name == "BONK" else 6
            price = out_amount / (10 ** decimals)
            
            # Get USDC price for USD conversion
            usdc_response = requests.get(usdc_url)
            if usdc_response.status_code == 200:
                usdc_data = usdc_response.json()
                usdc_amount = int(usdc_data["outAmount"]) / 1e6  # USDC has 6 decimals
                sol_price_usd = usdc_amount
                
                if token_name == "USDC":
                    return f"✅ USDC Price: {price:.2f} USDC/SOL (${sol_price_usd:.2f} per SOL)"
                else:
                    token_price_usd = (sol_price_usd / price) if price > 0 else 0
                    return f"✅ {token_name} Price: {price:,.0f} {token_name}/SOL (${token_price_usd:.8f} per {token_name})"
            else:
                return f"✅ {token_name} Price: {price:,.0f} {token_name}/SOL (USD price unavailable)"
                
        except Exception as e:
            return f"❌ {token_name} Price: Error - {str(e)}"
        
    def get_wallet_balance(self):
        """Get wallet SOL balance"""
        headers = {"Content-Type": "application/json"}
        if "?" in self.rpc_url:
            api_key = self.rpc_url.split("?")[1].split("=")[1]
            headers["Authorization"] = f"Bearer {api_key}"
            
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getBalance",
            "params": [str(self.wallet.pubkey())]
        }
        
        response = requests.post(self.rpc_url.split("?")[0], headers=headers, json=payload)
        result = response.json()
        
        if "result" in result:
            balance = result["result"]["value"] / 1e9
            return f"✅ Wallet Balance: {balance:.4f} SOL"
        return "❌ Wallet Balance: Error"
        
    def execute_trade(self, token_name: str, amount_sol: float = 0.01):
        """Execute a trade using Jupiter"""
        print(f"\n🔄 Trading {amount_sol} SOL for {token_name}...")
        
        # Get USDC price for USD value
        usdc_url = (
            f"https://quote-api.jup.ag/v6/quote?"
            f"inputMint=So11111111111111111111111111111111111111112"
            f"&outputMint={self.tokens['USDC']}"
            f"&amount=1000000000"
        )
        
        try:
            usdc_response = requests.get(usdc_url)
            if usdc_response.status_code == 200:
                usdc_data = usdc_response.json()
                sol_price_usd = int(usdc_data["outAmount"]) / 1e6
                usd_value = amount_sol * sol_price_usd
                print(f"USD Value: ${usd_value:.2f}")
        except:
            print("USD value calculation failed")
        
        # Get quote
        token_address = self.tokens[token_name]
        quote_url = (
            f"https://quote-api.jup.ag/v6/quote?"
            f"inputMint=So11111111111111111111111111111111111111112"
            f"&outputMint={token_address}"
            f"&amount={int(amount_sol * 1e9)}"
            f"&slippageBps=50"
        )
        
        quote_response = requests.get(quote_url)
        if quote_response.status_code != 200:
            return "❌ Trade Failed: Quote error"
            
        quote_data = quote_response.json()
        decimals = 5 if token_name == "BONK" else 6
        out_amount = int(quote_data["outAmount"]) / (10 ** decimals)
        
        print(f"Quote: {out_amount:,.0f} {token_name}")
        try:
            price_impact = float(quote_data.get('priceImpactPct', 0))
            print(f"Price Impact: {price_impact:.4f}%")
        except:
            print("Price Impact: Unable to calculate")
        
        # Get swap transaction
        swap_url = "https://quote-api.jup.ag/v6/swap"
        swap_data = {
            "quoteResponse": quote_data,
            "userPublicKey": str(self.wallet.pubkey()),
            "wrapUnwrapSOL": True,
            "computeUnitPriceMicroLamports": 1
        }
        
        swap_response = requests.post(swap_url, json=swap_data)
        if swap_response.status_code != 200:
            return "❌ Trade Failed: Swap error"
            
        # Transaction will be signed and sent by solana_client.py
        print(f"\n✅ Trade prepared! Use solana_client.py to execute:")
        print(f"python src/client/solana_client.py --action trade --token {token_address} --qty {amount_sol}")
        return "✅ Trade Setup Complete"

def run_demo():
    """Run the DeFi demo"""
    print("\n=== 🚀 Solana DeFi Demo ===")
    demo = DefiDemo()
    
    print(f"\n📡 Network: {demo.network}")
    print(f"👛 Wallet: {str(demo.wallet.pubkey())}")
    
    # 1. Check network status
    print(f"\n1️⃣ {demo.get_network_status()}")
    
    # 2. Get wallet balance
    print(f"2️⃣ {demo.get_wallet_balance()}")
    
    # 3. Check token prices
    print("\n3️⃣ Token Prices:")
    for token in demo.tokens:
        print(f"   {demo.get_token_price(token)}")
        
    # 4. Prepare a trade
    print("\n4️⃣ Trade Demo:")
    print(demo.execute_trade("BONK", 0.01))
    
    print("\n✨ Demo Complete!")
    print("Note: For actual trading, use solana_client.py with the command shown above.")

if __name__ == "__main__":
    run_demo() 