import asyncio
import json
from crewai import Agent, Task, Crew
from crewai_tools import SerperDevTool, WebsiteSearchTool, FileReadTool
import requests
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown

console = Console()

def create_tech_analysis_agent():
    """Create an AI agent specialized in tech trend analysis"""
    return {
        "name": "Tech Analyst",
        "description": "Expert AI agent for analyzing technology trends",
        "agents": {
            "analyst": {
                "role": "Technology Trend Analyst",
                "goal": "Analyze and predict technology trends with deep insights",
                "agent_tools": ["SerperDevTool", "WebsiteSearchTool"]
            }
        },
        "tasks": {
            "analyze": {
                "description": "Analyze current tech trends and make predictions",
                "agent": "analyst"
            }
        }
    }

def create_content_agent():
    """Create an AI agent specialized in content creation"""
    return {
        "name": "Content Creator",
        "description": "Expert AI agent for creating engaging content",
        "agents": {
            "writer": {
                "role": "Tech Content Strategist",
                "goal": "Create compelling content about technology trends",
                "agent_tools": ["FileReadTool"]
            }
        },
        "tasks": {
            "create": {
                "description": "Create engaging content based on tech analysis",
                "agent": "writer"
            }
        }
    }

async def run_demo():
    BASE_URL = "http://localhost:8000"
    console.print(Panel.fit("🚀 Starting AI Framework Demo", style="bold magenta"))

    # 1. Register Tools
    console.print("\n[bold blue]1. Registering AI Tools...[/bold blue]")
    tools = requests.get(f"{BASE_URL}/tool_search?query=search").json()
    console.print(Markdown(json.dumps(tools, indent=2)))

    # 2. Register Agents
    console.print("\n[bold blue]2. Creating Specialized AI Agents...[/bold blue]")
    
    # Register Tech Analyst
    response = requests.post(f"{BASE_URL}/save_agent", json=create_tech_analysis_agent())
    analyst_id = response.json()["agent_id"]
    console.print(f"✓ Tech Analyst created with ID: {analyst_id}")
    
    # Register Content Creator
    response = requests.post(f"{BASE_URL}/save_agent", json=create_content_agent())
    creator_id = response.json()["agent_id"]
    console.print(f"✓ Content Creator created with ID: {creator_id}")

    # 3. Execute Tech Analysis
    console.print("\n[bold blue]3. Executing Tech Trend Analysis...[/bold blue]")
    analysis = requests.get(
        f"{BASE_URL}/agent_call",
        params={
            "agent_id": analyst_id,
            "arguments": {
                "topic": "Latest breakthroughs in AI agents and autonomous systems",
                "depth": "deep",
                "perspective": "industry impact"
            }
        }
    ).json()
    
    console.print(Panel(Markdown(json.dumps(analysis, indent=2)), 
                       title="Tech Analysis Results", 
                       style="green"))

    # 4. Generate Content
    console.print("\n[bold blue]4. Generating Engaging Content...[/bold blue]")
    content = requests.get(
        f"{BASE_URL}/agent_call",
        params={
            "agent_id": creator_id,
            "arguments": {
                "analysis": analysis["result"],
                "style": "engaging and accessible",
                "format": "blog post"
            }
        }
    ).json()
    
    console.print(Panel(Markdown(content["result"]), 
                       title="Generated Content", 
                       style="cyan"))

    # 5. Demonstrate Real-time Updates
    console.print("\n[bold blue]5. Monitoring Agent Activities...[/bold blue]")
    import websockets
    
    async with websockets.connect(f"ws://localhost:8000/agent_ws") as websocket:
        await websocket.send(json.dumps({
            "type": "status_update",
            "data": {"message": "Monitoring agent activities..."}
        }))
        
        response = await websocket.recv()
        console.print(Panel(response, title="Real-time Update", style="yellow"))

if __name__ == "__main__":
    console.print("\n[bold red]🤖 AI Framework Demonstration[/bold red]\n")
    console.print("This demo showcases the power of collaborative AI agents\n")
    
    asyncio.run(run_demo())