import asyncio
import os
from typing import Dict, Any, Tuple
import requests
from rich.console import Console
from rich.panel import Panel
from rich.layout import Layout
from rich.live import Live
from rich.table import Table
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize rich console for beautiful output
console = Console()

class ZAgentDemo:
    def __init__(self):
        self.base_url = os.getenv("ZAPI_URL", "http://localhost:8000")
        self.z_api_url = os.getenv("Z_API_URL", "https://z-api.vistara.dev")
        self.agent_id = None
        self.console = Console()
        
    def check_z_api(self) -> Tuple[bool, str]:
        """Check if Z-API is accessible"""
        try:
            response = requests.get(f"{self.z_api_url}", timeout=5)
            response.raise_for_status()
            return True, "✅ Z-API is running"
        except requests.exceptions.ConnectionError:
            return False, "❌ Failed to connect to Z-API"
        except requests.exceptions.Timeout:
            return False, "❌ Z-API connection timed out"
        except Exception as e:
            return False, f"❌ Z-API check failed: {str(e)}"
        
    async def analyze_with_z_conscious(self, query: str) -> Dict[str, Any]:
        """Get analysis from Z-Conscious API"""
        try:
            response = requests.post(
                f"{self.z_api_url}/analyze",
                json={"query": query},
                timeout=20
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": f"Z-Analysis failed: {str(e)}"}
        
    def check_server(self) -> Tuple[bool, str]:
        """Check if the server is running and accessible"""
        try:
            response = requests.get(f"{self.base_url}/tool_search?query=solana", timeout=5)
            response.raise_for_status()
            return True, "✅ Server is running"
        except requests.exceptions.ConnectionError:
            return False, "❌ Failed to connect to server. Is it running?"
        except requests.exceptions.Timeout:
            return False, "❌ Server connection timed out"
        except Exception as e:
            return False, f"❌ Server check failed: {str(e)}"
        
    async def initialize_agents(self) -> str:
        """Create a swarm of specialized agents"""
        try:
            # Check server first
            server_ok, msg = self.check_server()
            if not server_ok:
                return msg
            
            # Get available tools
            response = requests.get(f"{self.base_url}/tool_search?query=solana", timeout=10)
            response.raise_for_status()
            tools = response.json()
            
            if not tools:
                return "❌ No Solana tools found on server"
            
            # Extract tool IDs
            tool_ids = [tool.get("payload", {}).get("id") for tool in tools]
            
            # Create agent with workflow configuration
            agent_response = requests.post(
                f"{self.base_url}/save_agent",
                json={
                    "name": "ZARA Demo Agent",
                    "description": "Solana operations agent",
                    "arguments": ["query"],
                    "agents": {
                        "solana_expert": {
                            "role": "Solana Operations Expert",
                            "goal": "Execute Solana operations and analysis",
                            "backstory": "Expert in Solana blockchain operations and analysis",
                            "agent_tools": tool_ids
                        }
                    },
                    "tasks": {
                        "execute_operation": {
                            "description": "Execute Solana operation: {query}",
                            "expected_output": "Operation result",
                            "agent": "solana_expert",
                            "context": []
                        }
                    }
                },
                timeout=15
            )
            agent_response.raise_for_status()
            
            try:
                response_data = agent_response.json()
                if "agent_id" not in response_data:
                    return "❌ Invalid agent ID in server response"
                self.agent_id = response_data["agent_id"]
                return "✨ Agent initialized successfully!"
            except (KeyError, requests.exceptions.JSONDecodeError) as e:
                return f"❌ Invalid response from server when creating agent: {str(e)}"
            
        except requests.exceptions.Timeout:
            return "❌ Request timed out. Server might be busy."
        except Exception as e:
            return f"❌ Initialization failed: {str(e)}"

    async def analyze_token(self, token_address: str) -> Dict[str, Any]:
        """Get comprehensive token analysis"""
        try:
            if not self.agent_id:
                return {"error": "Agents not initialized"}
            
            response = requests.post(
                f"{self.base_url}/agent_call",
                params={"agent_id": self.agent_id},
                json={"query": f"Perform comprehensive analysis of token {token_address}"},
                timeout=20
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": f"Analysis failed: {str(e)}"}

    async def monitor_network(self) -> Dict[str, Any]:
        """Monitor Solana network performance"""
        try:
            if not self.agent_id:
                return {"error": "Agents not initialized"}
                
            response = requests.post(
                f"{self.base_url}/agent_call",
                params={"agent_id": self.agent_id},
                json={"query": "Get current network performance metrics including TPS, slot times, and validator health"},
                timeout=20
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": f"Monitoring failed: {str(e)}"}

    async def showcase_demo(self):
        """Run an exciting showcase of the framework's capabilities"""
        # Create the layout
        layout = Layout()
        layout.split_column(
            Layout(name="header"),
            Layout(name="body"),
            Layout(name="footer")
        )

        # Header content
        header = Panel(
            "[bold cyan]🤖 Z-Agent Framework Demo[/bold cyan]\n"
            f"[dim]Framework: {self.base_url} | Z-API: {self.z_api_url}[/dim]",
            style="cyan"
        )
        layout["header"].update(header)

        # Initialize demo table
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Timestamp", style="dim")
        table.add_column("Component", style="cyan")
        table.add_column("Status", style="green")

        # Live display
        with Live(layout, refresh_per_second=4) as live:
            # Check Z-API status
            z_api_ok, z_api_msg = self.check_z_api()
            table.add_row(
                datetime.now().strftime("%H:%M:%S"),
                "Z-API Check",
                z_api_msg
            )
            layout["body"].update(table)
            
            if not z_api_ok:
                footer = Panel(
                    "[bold red]Demo limited: Z-API not available[/bold red]\n"
                    "[dim]Will continue with limited functionality[/dim]",
                    style="yellow"
                )
                layout["footer"].update(footer)
                await asyncio.sleep(2)

            # Check server status
            server_ok, server_msg = self.check_server()
            table.add_row(
                datetime.now().strftime("%H:%M:%S"),
                "Server Check",
                server_msg
            )
            layout["body"].update(table)
            
            if not server_ok:
                footer = Panel(
                    "[bold red]Demo failed: Server not available[/bold red]\n"
                    "[dim]Please make sure the Z-Agent Framework server is running[/dim]",
                    style="red"
                )
                layout["footer"].update(footer)
                await asyncio.sleep(5)
                return

            await asyncio.sleep(2)

            # Initialize agents
            init_result = await self.initialize_agents()
            table.add_row(
                datetime.now().strftime("%H:%M:%S"),
                "Agent Initialization",
                init_result
            )
            layout["body"].update(table)
            
            if "❌" in init_result:
                footer = Panel(
                    "[bold red]Demo failed during initialization[/bold red]\n"
                    "[dim]Please check the server logs for more details[/dim]",
                    style="red"
                )
                layout["footer"].update(footer)
                await asyncio.sleep(5)
                return

            await asyncio.sleep(2)

            # Z-Conscious Analysis
            if z_api_ok:
                table.add_row(
                    datetime.now().strftime("%H:%M:%S"),
                    "Z-Conscious Analysis",
                    "🧠 Getting deep insights..."
                )
                layout["body"].update(table)
                z_analysis = await self.analyze_with_z_conscious("Analyze the current state of Solana DeFi ecosystem")
                status = "✨ Insights received!" if "error" not in z_analysis else f"❌ {z_analysis['error']}"
                table.add_row(
                    datetime.now().strftime("%H:%M:%S"),
                    "Z-Conscious Analysis",
                    status
                )
                layout["body"].update(table)
                await asyncio.sleep(2)

            # Analyze ZARA token
            token_address = os.getenv("DEMO_TOKEN", "73UdJevxaNKXARgkvPHQGKuv8HCZARszuKW2LTL3pump")
            table.add_row(
                datetime.now().strftime("%H:%M:%S"),
                "Token Analysis",
                "🔍 Analyzing token..."
            )
            layout["body"].update(table)
            token_analysis = await self.analyze_token(token_address)
            status = "✅ Analysis complete!" if "error" not in token_analysis else f"❌ {token_analysis['error']}"
            table.add_row(
                datetime.now().strftime("%H:%M:%S"),
                "Token Analysis",
                status
            )
            layout["body"].update(table)
            await asyncio.sleep(2)

            # Monitor network
            table.add_row(
                datetime.now().strftime("%H:%M:%S"),
                "Network Monitoring",
                "📊 Monitoring Solana network..."
            )
            layout["body"].update(table)
            network_stats = await self.monitor_network()
            status = "✅ Network stats received!" if "error" not in network_stats else f"❌ {network_stats['error']}"
            table.add_row(
                datetime.now().strftime("%H:%M:%S"),
                "Network Monitoring",
                status
            )
            layout["body"].update(table)
            await asyncio.sleep(2)

            # Final status
            if any("❌" in row[2] for row in table.rows):
                footer = Panel(
                    "[bold yellow]Demo completed with some issues[/bold yellow]\n"
                    "[dim]Check the logs above for details[/dim]",
                    style="yellow"
                )
            else:
                footer = Panel(
                    "[bold green]Demo completed successfully![/bold green]\n"
                    "[dim]Showcased: Z-Conscious, Agent Swarm, Token Analysis, Network Monitoring[/dim]",
                    style="green"
                )
            layout["footer"].update(footer)

async def main():
    try:
        demo = ZAgentDemo()
        await demo.showcase_demo()
    except KeyboardInterrupt:
        console.print("\n[yellow]Demo interrupted by user[/yellow]")
    except Exception as e:
        console.print(f"\n[red]Demo failed: {str(e)}[/red]")

if __name__ == "__main__":
    asyncio.run(main()) 