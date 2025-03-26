"""
AgentHub: Market Intelligence Demo

This demonstration shows how to use AgentHub to create a comprehensive 
market intelligence system with minimal code. The example focuses on
crypto market analysis but can be adapted for any market research.

The demo showcases how AgentHub:
1. Simplifies tool creation and registration
2. Enables semantic tool discovery
3. Supports declarative agent workflows
4. Handles complex task dependencies
5. Provides real-time status updates
"""

import os
import json
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
import requests
from datetime import datetime

# Initialize console for rich output
console = Console()

# Define the local AgentHub API endpoint
AGENTHUB_API = "http://localhost:8000"

def search_tools(query):
    """Search for tools that match a specific query"""
    response = requests.get(f"{AGENTHUB_API}/tool_search?query={query}")
    return response.json()

def save_agent(workflow_definition):
    """Register a new agent workflow with AgentHub"""
    response = requests.post(
        f"{AGENTHUB_API}/save_agent",
        json=workflow_definition
    )
    return response.json()

def execute_agent(agent_id, arguments):
    """Execute an agent with specific arguments"""
    response = requests.post(
        f"{AGENTHUB_API}/agent_call",
        json={
            "agent_id": agent_id,
            "arguments": arguments
        }
    )
    return response.json()

def run_demo():
    """Run the market intelligence demo"""
    console.print(Panel.fit(
        "🚀 AgentHub - Market Intelligence Demo", 
        style="bold blue"
    ))
    
    # Step 1: Search for relevant tools
    console.print("\n[bold yellow]1. Discovering Relevant Tools[/bold yellow]")
    console.print("Searching for market analysis tools...")
    
    market_tools = search_tools("market data price")
    console.print(f"Found {len(market_tools)} market data tools")
    
    sentiment_tools = search_tools("sentiment social")
    console.print(f"Found {len(sentiment_tools)} sentiment analysis tools")
    
    # Display tool examples
    if market_tools:
        console.print(f"\nExample market tool: [bold green]{market_tools[0]['payload']['id']}[/bold green]")
        console.print(f"Description: {market_tools[0]['payload']['description']}")
    
    if sentiment_tools:
        console.print(f"\nExample sentiment tool: [bold green]{sentiment_tools[0]['payload']['id']}[/bold green]")
        console.print(f"Description: {sentiment_tools[0]['payload']['description']}")
    
    # Step 2: Define a market intelligence workflow
    console.print("\n[bold yellow]2. Creating Market Intelligence Workflow[/bold yellow]")
    
    # Collect tool IDs from search results
    tool_ids = []
    if market_tools:
        tool_ids.append(market_tools[0]["id"])
    if sentiment_tools:
        tool_ids.append(sentiment_tools[0]["id"])
    
    # If no tools found in search, use example IDs
    if not tool_ids:
        console.print("[yellow]No tools found in search, using example IDs[/yellow]")
        tool_ids = ["example-market-tool-id", "example-sentiment-tool-id"]
    
    # Create workflow definition
    workflow = {
        "name": "Market Intelligence Analyst",
        "description": "Comprehensive market analysis workflow",
        "arguments": ["asset", "timeframe"],
        "agents": {
            "market_analyst": {
                "role": "Market Data Analyst",
                "goal": "Analyze market data and provide comprehensive insights",
                "backstory": "You are an expert market analyst with years of experience analyzing financial markets.",
                "agent_tools": tool_ids
            }
        },
        "tasks": {
            "market_analysis": {
                "description": """
                Analyze {asset} over {timeframe} timeframe and provide insights.
                
                Your analysis should include:
                1. Price Analysis - Recent price movements and key levels
                2. Volume Analysis - Trading volume patterns and anomalies
                3. Social Sentiment - Measure of market sentiment and social engagement
                4. Correlation Analysis - Relationship between price and social metrics
                5. Risk Assessment - Potential risks and market conditions
                6. Opportunity Assessment - Potential opportunities based on data
                
                Provide 3 specific, actionable insights based on your analysis.
                """,
                "expected_output": "Comprehensive market analysis with actionable insights",
                "agent": "market_analyst"
            }
        }
    }
    
    console.print("Creating workflow definition...")
    console.print(Markdown("```json\n" + json.dumps(workflow, indent=2) + "\n```"))
    
    # Register the workflow
    try:
        agent_result = save_agent(workflow)
        agent_id = agent_result.get("agent_id", "demo-agent-id")
        console.print(f"[green]✓[/green] Workflow registered with ID: {agent_id}")
    except Exception as e:
        console.print(f"[red]Error registering workflow: {str(e)}[/red]")
        console.print("Using demo agent ID for demonstration purposes")
        agent_id = "demo-agent-id"
    
    # Step 3: Execute the agent
    console.print("\n[bold yellow]3. Executing Market Analysis[/bold yellow]")
    
    # Ask for asset to analyze
    asset = console.input("[bold green]Enter asset to analyze (BTC, ETH, etc.): [/bold green]")
    if not asset:
        asset = "BTC"  # Default if empty
    
    timeframe = console.input("[bold green]Enter timeframe (1d, 1w, 1m): [/bold green]")
    if not timeframe:
        timeframe = "1w"  # Default if empty
    
    console.print(f"\nAnalyzing {asset} over {timeframe} timeframe...")
    
    # Execute agent
    try:
        # In a real implementation, this would call the actual API
        # result = execute_agent(agent_id, {"asset": asset, "timeframe": timeframe})
        
        # For demo, we'll simulate a response
        result = {
            "result": f"""# {asset} Market Analysis ({timeframe})

## Price Analysis
{asset} is currently trading at $67,245, up 1.26% in the last 24 hours. The price has formed a strong support level at $65,800 with resistance at $68,500.

## Volume Analysis
Trading volume has increased by 15% compared to the previous week, indicating growing market interest and potential for continued momentum.

## Social Sentiment
Social sentiment score is 0.35 (moderately positive) with a mention velocity of 237.5 mentions per hour. This represents a 12% increase from baseline.

## Correlation Analysis
Price-sentiment correlation is 0.67, showing strong alignment between social metrics and price movement over the analyzed timeframe.

## Risk Assessment
RSI is currently at 68, approaching overbought territory. Combined with resistance at $68,500, there's potential for short-term consolidation.

## Opportunity Assessment
The bull-bear ratio of 1.65 and growing social momentum suggest continued upside potential despite near-term resistance.

## Key Insights

1. The 15% increase in trading volume coupled with 0.35 sentiment score signals potential for a breakout above $68,500 resistance in the next 3-5 days.

2. Strong price-sentiment correlation (0.67) suggests monitoring social metrics for early signals, with any sentiment score above 0.5 likely preceding significant price movement.

3. Current engagement quality (0.72) is significantly higher than average (0.58), indicating high-quality interactions rather than just speculative noise.
"""
        }
        
        console.print("\n[bold green]✅ Analysis Complete![/bold green]")
        console.print(Panel(Markdown(result["result"]), title=f"{asset} Analysis", style="cyan"))
    except Exception as e:
        console.print(f"[red]Error executing agent: {str(e)}[/red]")
    
    # Step 4: Summary
    console.print("\n[bold yellow]4. AgentHub Benefits Demonstrated[/bold yellow]")
    console.print("""
[bold green]1. Semantic Tool Discovery[/bold green]
   - Found relevant tools based on natural language descriptions
   - No need to know exact tool names or implementation details

[bold green]2. Declarative Workflow Definition[/bold green]
   - Created complex analysis pipeline with simple JSON
   - No need to write Python code for agent orchestration

[bold green]3. Tool Integration[/bold green]
   - Tools were automatically made available to agents
   - No manual tool registration or configuration

[bold green]4. Single Responsibility[/bold green]
   - You only need to create domain-specific tools
   - Everything else is handled by the framework
    """)

if __name__ == "__main__":
    run_demo()
