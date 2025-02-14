import requests
import json
from typing import Optional, Dict, Any

class SolanaClient:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.agent_id = None

    def _create_agent(self) -> None:
        """Create a Solana agent with all necessary tools"""
        # First, get available Solana tools
        response = requests.get(f"{self.base_url}/tool_search", params={"query": "solana"})
        response.raise_for_status()
        tools = response.json()

        # Create agent with Solana tools
        agent_response = requests.post(
            f"{self.base_url}/save_agent",
            json={
                "name": "Solana Operations Agent",
                "description": "Agent for executing various Solana blockchain operations",
                "arguments": ["query"],
                "agents": {
                    "solana_agent": {
                        "role": "Solana Blockchain Assistant",
                        "goal": "Execute various operations on Solana blockchain using agentipy tools",
                        "backstory": "A specialized blockchain assistant that uses agentipy tools for Solana operations",
                        "agent_tools": [
                            tool["id"] for tool in tools 
                            if tool["payload"]["id"].startswith("Solana")
                        ],
                    }
                },
                "tasks": {
                    "solana_task": {
                        "description": "{query}",
                        "expected_output": "Operation execution result",
                        "agent": "solana_agent"
                    }
                }
            }
        )
        agent_response.raise_for_status()
        self.agent_id = agent_response.json()["agent_id"]

    def _execute_query(self, query: str) -> Dict[str, Any]:
        """Execute a query using the agent"""
        if not self.agent_id:
            self._create_agent()
        
        response = requests.get(
            f"{self.base_url}/agent_call",
            params={"agent_id": self.agent_id},
            json={"query": query}
        )
        response.raise_for_status()
        return response.json()

    def get_network_tps(self) -> Dict[str, Any]:
        """Get current Solana network TPS"""
        return self._execute_query("Get current TPS of Solana network")

    def get_token_price(self, token_address: str) -> Dict[str, Any]:
        """Get price for a specific token"""
        return self._execute_query(f"Fetch price for token {token_address}")

    def trade_token(self, token_address: str, quantity: float, slippage: int = 50) -> Dict[str, Any]:
        """Execute a token trade"""
        return self._execute_query(
            f"Trade {quantity} qty to token {token_address} with {slippage} bps slippage"
        )

    def stake_sol(self, amount: float) -> Dict[str, Any]:
        """Stake SOL"""
        return self._execute_query(f"Stake {amount} SOL")

    def get_address_name(self, address: str) -> Dict[str, Any]:
        """Get name for a Solana address"""
        return self._execute_query(f"Get name for address {address}")

def main():
    # Initialize client
    client = SolanaClient()

    # Test 1: Get Network TPS
    print("\n1. Testing Get Network TPS:")
    try:
        result = client.get_network_tps()
        print(json.dumps(result, indent=2))
    except Exception as e:
        print(f"Error: {e}")

    # Test 2: Get Token Price (using a sample token address)
    print("\n2. Testing Get Token Price:")
    try:
        # Example USDC token address on devnet
        token_address = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
        result = client.get_token_price(token_address)
        print(json.dumps(result, indent=2))
    except Exception as e:
        print(f"Error: {e}")

    # Test 3: Get Address Name
    print("\n3. Testing Get Address Name:")
    try:
        # Example Solana address
        address = "vines1vzrYbzLMRdu58ou5XTby4qAqVRLmqo36NKPTg"
        result = client.get_address_name(address)
        print(json.dumps(result, indent=2))
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main() 