import requests
import json
import time

def test_tool_search():
    """Test the tool search endpoint"""
    print("\nTool Search Response:")
    response = requests.get("http://localhost:8000/tool_search", params={"query": "analysis"}, timeout=5)
    tools = response.json()
    print(json.dumps(tools, indent=2))
    return tools

def test_save_agent():
    """Test the save agent endpoint"""
    print("\nTrying to create agent with data:")
    agent_data = {
        "name": "Solana Agent Swarm",
        "description": "A swarm of agents for Solana operations",
        "arguments": ["query"],
        "agents": {
            "trader": {
                "role": "Solana Trader",
                "goal": "Execute trades and monitor prices on Solana",
                "backstory": "Expert in Solana DeFi trading and market analysis",
                "agent_tools": ["Solana Trade", "Solana Fetch Price"]
            },
            "validator": {
                "role": "Solana Validator",
                "goal": "Monitor network performance and manage staking",
                "backstory": "Experienced Solana validator operator",
                "agent_tools": ["Solana Get Tps", "Solana Stake"]
            },
            "explorer": {
                "role": "Solana Explorer",
                "goal": "Explore and analyze Solana addresses",
                "backstory": "Blockchain forensics and analytics expert",
                "agent_tools": ["Solana Get Address Name"]
            }
        },
        "tasks": {
            "trading": {
                "description": "Execute trade operations: {query}",
                "expected_output": "Trade execution result",
                "agent": "trader",
                "context": []
            },
            "network": {
                "description": "Monitor network and staking: {query}",
                "expected_output": "Network status and staking info",
                "agent": "validator",
                "context": []
            },
            "exploration": {
                "description": "Explore addresses: {query}",
                "expected_output": "Address information",
                "agent": "explorer",
                "context": []
            }
        }
    }
    print(json.dumps(agent_data, indent=2))
    
    try:
        response = requests.post(
            "http://localhost:8000/save_agent",
            json=agent_data,
            timeout=5
        )
        
        if response.status_code == 200:
            print("\nAgent swarm created successfully!")
            return response.json()["agent_id"]
        else:
            print(f"\nError creating agent swarm: {response.status_code}")
            print(response.text)
            return None
    except Exception as e:
        print(f"\nError creating agent swarm: {str(e)}")
        return None

def test_agent_call(agent_id):
    """Test the agent call endpoint with different Solana operations"""
    if not agent_id:
        print("\nSkipping agent call test - no agent_id")
        return
    
    test_queries = [
        "Get current TPS and stake info for validator ABC123",
        "Check price of SOL/USD and execute trade if below $100",
        "Get information about address 9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin"
    ]
    
    for query in test_queries:
        print(f"\nTrying to call agent with query: {query}")
        try:
            response = requests.post(
                "http://localhost:8000/agent_call",
                params={"agent_id": agent_id},
                json={"query": query},
                timeout=30  # Increased timeout for agent execution
            )
            if response.status_code == 200:
                print("\nAgent call successful!")
                print(json.dumps(response.json(), indent=2))
            else:
                print(f"\nError calling agent: {response.status_code}")
                print(response.text)
        except Exception as e:
            print(f"\nError calling agent: {str(e)}")
        
        # Wait a bit between calls
        time.sleep(2)

def main():
    print("Starting API tests...")
    test_tool_search()
    agent_id = test_save_agent()
    test_agent_call(agent_id)

if __name__ == "__main__":
    main() 