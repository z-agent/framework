"""
Advanced Solana Trading Alpha Demo
This script demonstrates sophisticated trading strategies using the Solana Agent Swarm.
"""

import os
import json
import requests
import time
from datetime import datetime
from typing import Dict, Any
from dotenv import load_dotenv

load_dotenv()

class TradingAlphaDemo:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.agent_id = None
        
    def create_agent(self):
        """Create an advanced trading agent with multiple capabilities"""
        workflow_request = {
            "name": "Solana Alpha Trading Agent",
            "description": "Advanced agent for executing sophisticated trading strategies",
            "arguments": ["query"],
            "agents": {
                "alpha_trader": {
                    "role": "Quantitative Trading Expert",
                    "goal": "Execute advanced trading strategies with optimal timing",
                    "backstory": "Expert quant trader specializing in MEV, arbitrage, and market making",
                    "agent_tools": [
                        "Solana Trade",
                        "Solana Fetch Price",
                        "Solana Get Tps",
                        "Solana Transfer"
                    ]
                }
            },
            "tasks": {
                "market_analysis": {
                    "description": "Analyze market conditions: {query}",
                    "expected_output": "Market analysis with trading signals",
                    "agent": "alpha_trader",
                    "context": []
                },
                "trade_execution": {
                    "description": "Execute optimal trades: {query}",
                    "expected_output": "Trade execution with performance metrics",
                    "agent": "alpha_trader",
                    "context": ["market_analysis"]
                }
            }
        }
        
        print("\n🚀 Initializing Alpha Trading Agent...")
        response = requests.post(
            f"{self.base_url}/save_agent",
            json=workflow_request
        )
        response.raise_for_status()
        self.agent_id = response.json()["agent_id"]
        print("✅ Agent initialized successfully")
        
    def execute_query(self, query: str) -> Dict[str, Any]:
        """Execute a query using the agent"""
        if not self.agent_id:
            self.create_agent()
            
        response = requests.post(
            f"{self.base_url}/agent_call",
            params={"agent_id": self.agent_id},
            json={"query": query}
        )
        response.raise_for_status()
        return response.json()

    def monitor_network_conditions(self) -> Dict[str, Any]:
        """Monitor network TPS and congestion for optimal trade timing"""
        print("\n📊 Analyzing Network Conditions...")
        result = self.execute_query("Get current TPS and assess network congestion")
        # Extract TPS from the result
        try:
            raw_text = str(result.get('raw', ''))
            tps = float([x for x in raw_text.split() if 'TPS' in x or 'tps' in x][0].split()[0])
            return {"tps": tps, "raw": result}
        except:
            return {"tps": 0, "raw": result}

    def analyze_token_price(self, token_address: str) -> Dict[str, Any]:
        """Analyze token price with technical indicators"""
        print(f"\n📈 Analyzing Token Price for {token_address}...")
        return self.execute_query(f"Fetch detailed price analysis for token {token_address}")

    def execute_arbitrage_strategy(self, token_address: str, amount: float) -> Dict[str, Any]:
        """Execute cross-market arbitrage strategy with better error handling"""
        print(f"\n🔄 Executing Arbitrage Strategy...")
        query = f"""
        Execute arbitrage for {token_address}:
        1. Get best buy price from Jupiter
        2. Get best sell price from Orca/Raydium
        3. Execute if profit > transaction cost
        4. Amount: {amount} tokens
        5. Max slippage: 1%
        """
        return self.execute_query(query)

    def execute_tps_based_trade(self, token_address: str, amount: float, min_tps: int = 2500) -> Dict[str, Any]:
        """Execute trade based on network TPS conditions"""
        print(f"\n🎯 Executing TPS-Based Trade Strategy...")
        query = f"Check TPS and if above {min_tps}, trade {amount} SOL to {token_address} with dynamic slippage"
        return self.execute_query(query)

    def execute_flash_loan_arbitrage(self, token_address: str, amount: float) -> Dict[str, Any]:
        """Execute flash loan arbitrage strategy"""
        print(f"\n⚡ Executing Flash Loan Arbitrage Strategy...")
        query = f"Execute flash loan arbitrage with {amount} SOL using {token_address} as target"
        return self.execute_query(query)

    def monitor_liquidation_opportunities(self, token_address: str, health_factor_threshold: float = 1.1) -> Dict[str, Any]:
        """Monitor positions close to liquidation for protection or profit opportunities"""
        print(f"\n🛡️ Monitoring Liquidation Opportunities...")
        query = f"Analyze positions with health factor below {health_factor_threshold} for token {token_address}"
        return self.execute_query(query)

    def protect_position(self, token_address: str, health_factor: float, collateral_amount: float) -> Dict[str, Any]:
        """Protect position from liquidation by adding collateral or reducing debt"""
        print(f"\n🔒 Protecting Position...")
        query = f"Position health factor {health_factor} for {token_address}. Add {collateral_amount} SOL as collateral if needed"
        return self.execute_query(query)

    def analyze_mev_opportunity(self, token_address: str, base_amount: float = 0.1) -> Dict[str, Any]:
        """Analyze MEV opportunities including price impact and cross-DEX arbitrage"""
        print(f"\n🔍 Analyzing MEV Opportunities...")
        network_status = self.monitor_network_conditions()
        tps = network_status.get('tps', 0)
        
        query = f"""
        Analyze MEV for {token_address}:
        1. Get Jupiter quote for {base_amount} tokens
        2. Compare with Orca and Raydium direct routes
        3. Calculate potential arbitrage profit
        4. Factor in execution costs and slippage
        5. Consider current TPS of {tps}
        """
        return self.execute_query(query)

def run_alpha_demo():
    """Quick arbitrage analysis demo on mainnet"""
    print("\n=== 🌟 Quick Arbitrage Analysis Demo ===")
    print(f"🔗 Network: {os.getenv('SOLANA_RPC_URL', 'mainnet')}")
    print(f"⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        demo = TradingAlphaDemo()
        
        # Analyze popular tokens for arbitrage
        tokens = {
            "BONK": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
            "JTO": "jtojtomepa8beP8AuQc6eXt5FriJwfkmzuLzWWUdSbr",
            "SAMO": "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU"
        }
        
        print("\n📊 Quick Market Analysis")
        for name, address in tokens.items():
            print(f"\n🔍 Analyzing {name}...")
            
            # Get current price and liquidity
            query = f"""
            Quick arbitrage check for {name} ({address}):
            1. Get current price on Jupiter, Orca, Raydium
            2. Check liquidity depth
            3. Calculate potential arbitrage (accounting for 0.3% fees)
            4. Minimum profitable trade size
            """
            
            result = demo.execute_query(query)
            print(f"{name} Analysis:", json.dumps(result, indent=2))
            
            # If profitable opportunity found, show execution path
            if "profit" in str(result).lower() and "error" not in str(result).lower():
                print(f"\n💰 Profitable {name} Opportunity Found!")
                print("- Buy from:", str(result).split("Buy from")[1].split()[0])
                print("- Sell on:", str(result).split("Sell on")[1].split()[0])
                print("- Estimated profit %:", str(result).split("profit")[1].split("%")[0].strip())
                print("- Min trade size:", str(result).split("size:")[1].split()[0])
                print("\nExecution path:")
                print("1. Swap on DEX with lower price")
                print("2. Swap back on DEX with higher price")
                print("3. Net profit after fees")
            
            time.sleep(1)  # Rate limit between requests
            
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
    finally:
        print("\n✨ Analysis Complete")
        print("Note: Real arbitrage requires careful execution, proper slippage settings,")
        print("      and consideration of transaction costs and market impact.")

if __name__ == "__main__":
    run_alpha_demo() 