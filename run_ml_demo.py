"""
Run the ML Trading Insights Demo
This script demonstrates the power of ML-enhanced trading analysis with NLP interface
"""

import os
import sys
import asyncio
from rich.console import Console
from rich.panel import Panel

# Add project root to Python path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.append(project_root)

from demos.ml_insights_demo import MLInsightsDemo

console = Console()

async def main():
    """Run the enhanced ML Trading Insights Demo"""
    demo = MLInsightsDemo()
    
    # Introduction
    console.print(Panel.fit(
        "[bold magenta]🤖 ML-Enhanced Trading Assistant[/bold magenta]\n"
        "Combining ML insights with natural language understanding for smarter trading",
        style="magenta"
    ))
    
    # 1. Market Comparison
    console.print("\n[bold cyan]1. Market Analysis[/bold cyan]")
    await demo.show_market_comparison(["SOL", "JTO", "BONK", "APES"])
    
    # 2. Detailed Token Analysis
    console.print("\n[bold cyan]2. Token Deep Dives[/bold cyan]")
    
    # SOL Analysis
    await demo.show_real_world_example(
        "SOL",
        "SOL Technical Analysis",
        "ML-enhanced technical analysis with breakout detection"
    )
    
    # JTO Analysis
    await demo.show_real_world_example(
        "JTO",
        "JTO Risk Analysis",
        "Deep dive into risk factors and market impact"
    )
    
    # BONK Analysis
    await demo.show_real_world_example(
        "BONK",
        "BONK Sentiment Analysis",
        "Social sentiment and market momentum analysis"
    )
    
    # 3. NLP Trading Interface Demo
    console.print("\n[bold cyan]3. Natural Language Trading Interface[/bold cyan]")
    
    example_commands = [
        "Analyze SOL market conditions and tell me if it's a good time to buy",
        "What's the risk level for trading JTO right now?",
        "Show me entry points for BONK with stop loss levels",
        "Compare market momentum between SOL and JTO"
    ]
    
    for command in example_commands:
        console.print(f"\n[bold green]User Command:[/bold green] {command}")
        response = await demo.process_nlp_command(command)
        
        if "error" not in response:
            console.print(Panel(
                response["interpretation"],
                title="🤖 AI Analysis",
                style="blue"
            ))
        else:
            console.print(f"[red]Error: {response['error']}[/red]")
    
    # Summary of Benefits
    console.print(Panel(
        "[bold green]Why Use ML-Enhanced Trading?[/bold green]\n\n"
        "1. [bold]Smarter Decision Making[/bold]\n"
        "   • ML-powered price predictions\n"
        "   • Risk-aware trading signals\n"
        "   • Market impact analysis\n\n"
        "2. [bold]Natural Language Interface[/bold]\n"
        "   • Simple English commands\n"
        "   • Contextual understanding\n"
        "   • Clear explanations\n\n"
        "3. [bold]Risk Management[/bold]\n"
        "   • Multi-factor risk scoring\n"
        "   • Position sizing guidance\n"
        "   • Stop loss recommendations\n\n"
        "4. [bold]Market Intelligence[/bold]\n"
        "   • Social sentiment analysis\n"
        "   • Momentum detection\n"
        "   • Pattern recognition",
        title="🎯 Benefits",
        style="green"
    ))

if __name__ == "__main__":
    asyncio.run(main()) 