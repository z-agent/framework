import json
import requests
import argparse
import sys

def main():
    parser = argparse.ArgumentParser(description='Solana Blockchain Client')
    parser.add_argument('--host', default='localhost', help='API host')
    parser.add_argument('--port', default='8000', help='API port')
    parser.add_argument('--token', required=True, help='Token address to trade')
    parser.add_argument('--qty', type=float, default=1.0, help='Quantity to trade')
    parser.add_argument('--slippage', type=int, default=50, help='Slippage in bps')
    
    args = parser.parse_args()
    base = f"http://{args.host}:{args.port}"

    try:
        # Fetch Solana tools
        tools_response = requests.get(f"{base}/tool_search?query=solana")
        tools_response.raise_for_status()
        tools = tools_response.json()

        # Create agent with agentipy tools
        agent_response = requests.post(
            f"{base}/save_agent",
            json={
                "name": "Solana Trading Agent",
                "description": "Agent for executing Solana trades",
                "arguments": ["query"],
                "agents": {
                    "solana_agent": {
                        "role": "Solana Trading Assistant",
                        "goal": "Execute trades on Solana blockchain using agentipy tools",
                        "backstory": "A specialized trading assistant that uses agentipy tools for Solana operations",
                        "agent_tools": [
                            tool["id"]
                            for tool in tools
                            if tool["payload"]["id"].startswith("Solana")
                        ],
                    }
                },
                "tasks": {
                    "trade_task": {
                        "description": "{query}",
                        "expected_output": "Trade execution result",
                        "agent": "solana_agent"
                    }
                }
            }
        )
        agent_response.raise_for_status()
        agent = agent_response.json()

        # Execute trade using agentipy tools
        query = f"Trade {args.qty} qty to token {args.token} with {args.slippage} bps slippage"
        call_response = requests.post(
            f"{base}/agent_call?agent_id={agent['agent_id']}",
            json={"query": query}
        )
        call_response.raise_for_status()
        print(json.dumps(call_response.json(), indent=2))

    except requests.exceptions.RequestException as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {str(e)}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
