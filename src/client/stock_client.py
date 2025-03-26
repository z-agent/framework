import json
import requests
import argparse
import sys

def main():
    parser = argparse.ArgumentParser(description='Stock Analysis Client')
    parser.add_argument('--host', default='localhost', help='API host')
    parser.add_argument('--port', default='8000', help='API port')
    parser.add_argument('--symbol', required=True, help='Stock symbol to analyze')
    parser.add_argument('--analysis', choices=['fundamental', 'technical', 'risk', 'all'], 
                       default='all', help='Type of analysis to perform')
    
    args = parser.parse_args()
    base = f"http://{args.host}:{args.port}"

    try:
        # Fetch stock analysis tools
        tools_response = requests.get(f"{base}/tool_search?query=stock analysis")
        tools_response.raise_for_status()
        tools = tools_response.json()

        # Create agent with stock analysis tools
        agent_response = requests.post(
            f"{base}/save_agent",
            json={
                "name": "Stock Analysis Agent",
                "description": "Agent for performing comprehensive stock analysis",
                "arguments": ["query"],
                "agents": {
                    "analyst": {
                        "role": "Stock Market Analyst",
                        "goal": "Perform detailed stock analysis using various analytical tools",
                        "backstory": "An experienced financial analyst specializing in comprehensive stock analysis",
                        "agent_tools": [
                            "FundamentalAnalysis",
                            "TechnicalAnalysis",
                            "RiskAssessment"
                        ],
                    }
                },
                "tasks": {
                    "analysis_task": {
                        "description": "{query}",
                        "expected_output": "Detailed stock analysis report",
                        "agent": "analyst"
                    }
                }
            }
        )
        agent_response.raise_for_status()
        agent = agent_response.json()

        # Prepare analysis query based on user input
        if args.analysis == 'fundamental':
            query = f"Perform fundamental analysis for {args.symbol}"
        elif args.analysis == 'technical':
            query = f"Perform technical analysis for {args.symbol}"
        elif args.analysis == 'risk':
            query = f"Assess risk factors for {args.symbol}"
        else:
            query = f"Perform comprehensive analysis (fundamental, technical, and risk) for {args.symbol}"

        # Execute analysis
        call_response = requests.get(
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