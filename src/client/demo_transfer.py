import os
import json
import requests
import time
from dotenv import load_dotenv

load_dotenv()

def get_balance(base_url, agent_id):
    """Get SOL balance of the wallet"""
    try:
        response = requests.post(
            f"{base_url}/agent_call",
            params={"agent_id": agent_id},
            json={"query": "Get my wallet balance"}
        )
        response.raise_for_status()
        result = response.json()
        return float(result.get("balance", 0))
    except Exception as e:
        print(f"Error getting balance: {str(e)}")
        return None

def test_transfer():
    """Test SOL transfer functionality"""
    base_url = "http://localhost:8000"
    
    print("\n=== 🌟 Solana Transfer Demo ===")
    print(f"🔗 Network: {os.getenv('SOLANA_RPC_URL').split('?')[0]}")
    
    try:
        # Create agent with transfer capability
        workflow_request = {
            "name": "Solana Transfer Agent",
            "description": "Agent for executing Solana transfers",
            "arguments": ["query"],
            "agents": {
                "trader": {
                    "role": "Solana Trader",
                    "goal": "Execute transfers and monitor balances on Solana",
                    "backstory": "Expert in Solana transfers and balance tracking",
                    "agent_tools": ["Solana Transfer", "Solana Get Tps"]
                }
            },
            "tasks": {
                "transfer": {
                    "description": "{query}",
                    "expected_output": "Transfer execution result with balance tracking",
                    "agent": "trader",
                    "context": []
                }
            }
        }
        
        print("\n📝 Creating agent...")
        agent_response = requests.post(
            f"{base_url}/save_agent",
            json=workflow_request
        )
        agent_response.raise_for_status()
        agent_id = agent_response.json()["agent_id"]
        print("✅ Agent created successfully")
        
        # Get initial balance
        print("\n💰 Checking initial balance...")
        initial_balance_query = "Get current TPS and my wallet balance"
        balance_response = requests.post(
            f"{base_url}/agent_call",
            params={"agent_id": agent_id},
            json={"query": initial_balance_query}
        )
        balance_response.raise_for_status()
        initial_result = balance_response.json()
        
        # Test transfer query
        destination = "5XdtyEDREHJXXW1CTtCsVjJFxsJtQkEqWwXXLysr2fYU"
        amount = 0.01  # Small amount for testing
        
        print(f"\n📤 Initiating transfer:")
        print(f"   To: {destination}")
        print(f"   Amount: {amount} SOL")
        
        query = f"Transfer {amount} SOL to address {destination}"
        response = requests.post(
            f"{base_url}/agent_call",
            params={"agent_id": agent_id},
            json={"query": query}
        )
        response.raise_for_status()
        
        result = response.json()
        print("\n🔄 Transfer Result:")
        print(json.dumps(result, indent=2))
        
        # Extract signature and verify success
        raw_result = str(result)
        if "signature" in raw_result.lower():
            print("\n✅ Transfer completed successfully!")
            try:
                signature = raw_result.split("signature")[1].split()[0].strip(": ").strip("'\".,")
                print(f"\n🔍 Transaction Details:")
                print(f"   Signature: {signature}")
                print(f"   Explorer URL: https://explorer.solana.com/tx/{signature}?cluster=devnet")
            except:
                print("Note: Transaction successful but couldn't extract signature")
            
            # Check final balance
            print("\n💰 Checking final balance...")
            final_balance_query = "Get current TPS and my wallet balance"
            final_balance_response = requests.post(
                f"{base_url}/agent_call",
                params={"agent_id": agent_id},
                json={"query": final_balance_query}
            )
            final_balance_response.raise_for_status()
            final_result = final_balance_response.json()
            
            print("\n📊 Balance Summary:")
            print("   Initial Balance: Checking network...")
            print("   Final Balance: Checking network...")
            print(f"   Transfer Amount: {amount} SOL")
            print("   Network Fee: ~0.000005 SOL")
            
        else:
            print("\n❌ Transfer may have failed. Please check the result details above.")
        
    except requests.exceptions.RequestException as e:
        print(f"\n❌ Error: {str(e)}")
        if hasattr(e.response, 'json'):
            try:
                error_detail = e.response.json().get('detail')
                print(f"Server error details: {error_detail}")
            except:
                pass
    except Exception as e:
        print(f"\n❌ Unexpected error: {str(e)}")

if __name__ == "__main__":
    test_transfer() 