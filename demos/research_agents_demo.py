"""
Research Agents Demo
Demonstrates the capabilities of AI-powered research agents
"""

import asyncio
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from datetime import datetime
from typing import Dict, Any
import logging

from src.services.research_service import ResearchService, ResearchRequest

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

console = Console()

class ResearchAgentsDemo:
    def __init__(self):
        """Initialize the research agents demo"""
        self.research_service = ResearchService()
        
    async def demo_trending_analysis(self):
        """Demo trending topics analysis"""
        console.print("\n[bold cyan]Analyzing Trending Topics[/bold cyan]")
        
        try:
            # Create research request
            request = ResearchRequest(
                user_id="KaranVaidya6",
                topics=["crypto", "defi", "ai"],
                lookback_days=7
            )
            print(f"Request: {request}")
            
            # Get social summary
            summary = await self.research_service.get_social_summary(request)
            print(f"Summary atrending : {summary}")
            if "error" not in summary:
                self._display_social_summary(summary)
            else:
                console.print(f"[red]Error getting social summary: {summary['error']}[/red]")
                
        except Exception as e:
            logger.error(f"Error in trending analysis: {str(e)}")
            console.print(f"[red]Error in trending analysis: {str(e)}[/red]")
            
    async def demo_social_research(self):
        """Demo social media research"""
        console.print("\n[bold cyan]Analyzing Social Media Trends[/bold cyan]")
        
        try:
            # Create research request
            request = ResearchRequest(
                user_id="demo_user",
                token_symbol="SOL",
                lookback_days=7,
                min_engagement=100
            )
            
            # Get social research
            research = await self.research_service.get_social_summary(request)
            
            if "error" not in research:
                self._display_social_summary(research)
            else:
                console.print(f"[red]Error in social research: {research['error']}[/red]")
                
        except Exception as e:
            logger.error(f"Error in social research: {str(e)}")
            console.print(f"[red]Error in social research: {str(e)}[/red]")
            
    async def demo_coin_research(self):
        """Demo coin research"""
        console.print("\n[bold cyan]Analyzing Token Fundamentals[/bold cyan]")
        
        try:
            # Create research request
            request = ResearchRequest(
                user_id="_mayurc",
                token_symbol="ZARA"
            )
            
            # Get coin research
            research = await self.research_service.research_coin(request)
            print(f"Research: {research}\n\njeeerere")
            
            if "error" not in research:
                self._display_coin_research(research)
            else:
                console.print(f"[red]Error in coin research: {research['error']}[/red]")
                
        except Exception as e:
            logger.error(f"Error in coin research: {str(e)}")
            console.print(f"[red]Error in coin research: {str(e)}[/red]")
            
    def _display_social_summary(self, summary: Dict[str, Any]):
        """Display social media analysis summary"""
        print(f"Summary: {summary}\n\n")
        # Topics table
        if "topics" in summary:
            table = Table(title="🔥 Trending Topics")
            table.add_column("Topic", style="cyan")
            table.add_column("Category", style="yellow")
            table.add_column("Sentiment", style="green")
            
            for topic in summary["topics"]:
                sentiment = "🟢" if topic["sentiment"] > 0 else "🔴" if topic["sentiment"] < 0 else "⚪"
                table.add_row(
                    topic["topic"],
                    topic["category"],
                    sentiment
                )
                
            console.print(table)
            
        # Key insights
        if "key_insights" in summary:
            console.print(Panel(
                "\n".join(f"• {insight}" for insight in summary["key_insights"]),
                title="💡 Key Insights",
                style="blue"
            ))
            
        # Top influencers
        if "top_influencers" in summary:
            table = Table(title="👥 Top Influencers")
            table.add_column("Name", style="cyan")
            table.add_column("Score", style="yellow")
            
            for influencer in summary["top_influencers"]:
                table.add_row(
                    influencer["name"],
                    f"{influencer['influence_score']:.2f}"
                )
                
            console.print(table)
            
    def _display_coin_research(self, research: Dict[str, Any]):
        """Display coin research results"""
        # Business model
        if "business_model" in research:
            console.print(Panel(
                "\n".join(
                    f"• {key}: {value}"
                    for key, value in research["business_model"].items()
                ),
                title="💼 Business Model",
                style="blue"
            ))
            
        # Team analysis
        if "team_analysis" in research:
            console.print(Panel(
                "\n".join(
                    f"• {key}: {value}"
                    for key, value in research["team_analysis"].items()
                ),
                title="👥 Team Analysis",
                style="green"
            ))
            
        # Tokenomics
        if "tokenomics" in research:
            table = Table(title="🪙 Tokenomics")
            table.add_column("Metric", style="cyan")
            table.add_column("Value", style="yellow")
            
            for key, value in research["tokenomics"].items():
                table.add_row(key, str(value))
                
            console.print(table)
            
        # Risk factors
        if "risk_factors" in research:
            console.print(Panel(
                "\n".join(
                    f"• {risk['name']}: {risk['description']}"
                    for risk in research["risk_factors"]
                ),
                title="⚠️ Risk Factors",
                style="red"
            ))
            
        # Social metrics
        if "social_metrics" in research:
            table = Table(title="📊 Social Metrics")
            table.add_column("Metric", style="cyan")
            table.add_column("Value", style="yellow")
            table.add_column("Change", style="green")
            
            for key, value in research["social_metrics"].items():
                if isinstance(value, dict):
                    table.add_row(
                        key,
                        str(value.get("value", "N/A")),
                        f"{value.get('change', 0):+.1%}"
                    )
                else:
                    table.add_row(key, str(value), "N/A")
                    
            console.print(table)

async def main():
    """Run the research agents demo"""
    try:
        # Show welcome message
        console.print(Panel.fit(
            "[bold magenta]🤖 AI Research Agents Demo[/bold magenta]\n"
            "Showcasing advanced research capabilities with x.ai integration",
            style="magenta"
        ))
        
        # Initialize demo
        demo = ResearchAgentsDemo()
        
        # Run demos
        # await demo.demo_trending_analysis()
        # await demo.demo_social_research()
        await demo.demo_coin_research()
        
        # Show value proposition
        # console.print(Panel(
        #     "[bold green]Why Use AI Research Agents?[/bold green]\n\n"
        #     "1. [bold]Real-time Trend Analysis[/bold]\n"
        #     "   • Instant insights from social media\n"
        #     "   • Sentiment tracking across platforms\n"
        #     "   • Early trend detection\n\n"
        #     "2. [bold]Comprehensive Research[/bold]\n"
        #     "   • Deep dive token analysis\n"
        #     "   • Team and tokenomics evaluation\n"
        #     "   • Risk assessment\n\n"
        #     "3. [bold]Actionable Insights[/bold]\n"
        #     "   • Clear recommendations\n"
        #     "   • Risk-aware analysis\n"
        #     "   • Performance metrics\n\n"
        #     "4. [bold]Time Efficiency[/bold]\n"
        #     "   • Automated data collection\n"
        #     "   • Real-time processing\n"
        #     "   • Instant insights",
        #     title="🎯 Benefits",
        #     style="green"
        # ))

    except Exception as e:
        logger.error(f"Error in demo: {str(e)}", exc_info=True)
        console.print(f"[red]Error in demo: {str(e)}[/red]")

if __name__ == "__main__":
    asyncio.run(main()) 