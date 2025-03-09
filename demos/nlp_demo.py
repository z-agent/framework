"""
DeFi NLP Demo - Making DeFi Simple and Safe
This demo shows how natural language makes complex DeFi operations accessible to everyone.
"""

import asyncio
import httpx
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.markdown import Markdown
from rich.progress import Progress
import time
from typing import Dict, Any

console = Console()

class DeFiDemo:
    def __init__(self, api_url: str = "http://localhost:8000"):
        self.api_url = api_url
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def process_command(self, text: str) -> Dict[str, Any]:
        """Send command to NLP service"""
        try:
            response = await self.client.post(
                f"{self.api_url}/nlp/process",
                json={
                    "text": text,
                    "context": {
                        "chain_id": "mainnet-beta",
                        "risk_level": "medium"
                    }
                }
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            console.print(f"[red]Error: {str(e)}[/red]")
            raise

    def display_response(self, scenario: str, command: str, response: Dict[str, Any]):
        """Display the response with clear value proposition"""
        # Scenario header
        console.print(Panel(
            f"[bold blue]{scenario}[/bold blue]",
            style="blue"
        ))
        
        # User input
        console.print(Panel(
            f"[bold green]User Says:[/bold green] {command}",
            title="👤 Natural Language Input",
            style="green"
        ))
        
        # System understanding
        if 'explanation' in response:
            console.print(Panel(
                f"[bold]System Understanding:[/bold]\n{response['explanation']}",
                title="🧠 AI Comprehension",
                style="cyan"
            ))
        
        # Action parameters
        if response.get('action_params'):
            table = Table(title="🎯 Detected Parameters")
            table.add_column("Parameter", style="cyan")
            table.add_column("Value", style="yellow")
            table.add_column("Safety Check", style="green")
            
            for key, value in response['action_params'].items():
                if key != 'execution':
                    safety = "✅" if self._validate_param(key, value) else "⚠️"
                    table.add_row(key, str(value), safety)
            
            console.print(table)
        
        # Safety suggestions
        if response.get('suggestions'):
            suggestions = response['suggestions']
            suggestion_text = ""
            
            if 'safety' in suggestions:
                suggestion_text += "\n[bold red]Safety Measures:[/bold red]\n"
                for tip in suggestions['safety']:
                    suggestion_text += f"• 🛡️ {tip}\n"
            
            if 'alternatives' in suggestions:
                suggestion_text += "\n[bold yellow]Smart Alternatives:[/bold yellow]\n"
                for alt in suggestions['alternatives']:
                    suggestion_text += f"• 💡 {alt}\n"
            
            console.print(Panel(
                suggestion_text,
                title="🔒 Risk Management & Optimization",
                style="yellow"
            ))
        
        console.print("\n")

    def _validate_param(self, key: str, value: Any) -> bool:
        """Basic parameter validation"""
        if key == "amount":
            return isinstance(value, (int, float)) and value > 0
        elif key == "token":
            return isinstance(value, str) and len(value) > 0
        elif key == "slippage":
            return isinstance(value, (int, float)) and 0 <= value <= 100
        return True

async def run_demo():
    """Run an interactive demo showcasing practical DeFi use cases"""
    demo = DeFiDemo()
    
    console.print(Panel.fit(
        "[bold magenta]🤖 DeFi Made Simple - Natural Language Interface[/bold magenta]\n"
        "Showcasing how AI makes DeFi accessible and safe",
        style="magenta"
    ))
    
    scenarios = [
        {
            "title": "1. Smart Trade Execution",
            "description": "Execute trades with built-in safety checks and MEV protection",
            "command": "buy 50 SOL with max slippage 0.5% and MEV protection",
        },
        {
            "title": "2. Risk-Aware Portfolio Management",
            "description": "Intelligent portfolio rebalancing with risk assessment",
            "command": "rebalance my portfolio to reduce risk, keep 30% in SOL",
        },
        {
            "title": "3. Smart DeFi Strategy",
            "description": "Optimized yield farming with risk considerations",
            "command": "find the safest yield farming opportunity for 1000 USDC",
        },
        {
            "title": "4. Market Analysis",
            "description": "Real-time market insights with risk indicators",
            "command": "analyze SOL price trend and tell me if it's a good time to buy",
        },
        {
            "title": "5. Gas Optimization",
            "description": "Smart transaction timing and gas optimization",
            "command": "swap 1000 USDC to SOL when gas fees are low",
        }
    ]
    
    for scenario in scenarios:
        console.print(f"\n[bold]{scenario['title']}[/bold]")
        console.print(scenario['description'])
        
        with Progress() as progress:
            task = progress.add_task("Processing...", total=100)
            
            # Process the command
            for step in range(0, 101, 20):
                progress.update(task, completed=step)
                await asyncio.sleep(0.2)
            
            response = await demo.process_command(scenario['command'])
            progress.update(task, completed=100)
        
        demo.display_response(scenario['title'], scenario['command'], response)
        await asyncio.sleep(1)
    
    # Value proposition summary
    console.print(Panel(
        "[bold green]Why Use Natural Language for DeFi?[/bold green]\n\n"
        "1. [bold]Safety First:[/bold]\n"
        "   • Automatic risk assessment\n"
        "   • Built-in safety checks\n"
        "   • MEV protection\n\n"
        "2. [bold]Simplicity:[/bold]\n"
        "   • No complex interfaces\n"
        "   • Natural communication\n"
        "   • Guided decision making\n\n"
        "3. [bold]Intelligence:[/bold]\n"
        "   • Smart parameter selection\n"
        "   • Market-aware timing\n"
        "   • Risk-optimized strategies\n\n"
        "4. [bold]Time Efficiency:[/bold]\n"
        "   • Quick execution\n"
        "   • Automated optimization\n"
        "   • Real-time adaptations\n",
        title="🎯 Benefits",
        style="green"
    ))

if __name__ == "__main__":
    console.print("\n[bold]🚀 Starting DeFi NLP Demo...[/bold]\n")
    asyncio.run(run_demo()) 