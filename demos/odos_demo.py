"""
Odos Protocol Integration Demo
Demonstrates the capabilities of Odos swap routing and optimization
"""

import asyncio
import os
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress
from rich.markdown import Markdown
from datetime import datetime
from typing import Dict, Any
import logging

from src.services.odos_service import OdosService, OdosSwapRequest

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

console = Console()

# Sample wallet address for demo
DEMO_WALLET = "0x1234567890123456789012345678901234567890"  # Replace with your wallet

# Token addresses for common tokens on Ethereum
ETH = "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE"
USDC = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"
WETH = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"
DAI = "0x6B175474E89094C44Da98b954EedeAC495271d0F"

class OdosDemo:
    def __init__(self):
        """Initialize the Odos demo"""
        self.odos_service = OdosService()
        self.wallet_address = os.getenv("DEMO_WALLET_ADDRESS", DEMO_WALLET)
        
    async def close(self):
        """Close the service connections"""
        await self.odos_service.close()
        
    async def demo_supported_tokens(self):
        """Demo listing supported tokens"""
        console.print("\n[bold cyan]Fetching Supported Tokens[/bold cyan]")
        
        with Progress() as progress:
            task = progress.add_task("[green]Fetching tokens...", total=1)
            
            try:
                # Get a list of supported tokens
                tokens = await self.odos_service.list_supported_tokens()
                progress.update(task, completed=1)
                
                # Create a table to display tokens
                table = Table(title="Supported Tokens on Odos")
                table.add_column("Symbol", style="cyan")
                table.add_column("Name", style="green")
                table.add_column("Address", style="blue")
                table.add_column("Price (USD)", style="yellow")
                
                # Display the first 10 tokens
                for token in tokens[:10]:
                    table.add_row(
                        token.get("symbol", "Unknown"),
                        token.get("name", "Unknown"),
                        token.get("address", "Unknown")[:10] + "...",
                        f"${token.get('price_usd', 0):.4f}" if token.get('price_usd') else "N/A"
                    )
                    
                console.print(table)
                console.print(f"[green]Total tokens supported: {len(tokens)}[/green]")
                
            except Exception as e:
                progress.update(task, completed=1)
                logger.error(f"Error in supported tokens demo: {str(e)}")
                console.print(f"[red]Error: {str(e)}[/red]")
                
    async def demo_token_swap_quote(self):
        """Demo getting a token swap quote"""
        console.print("\n[bold cyan]Getting Token Swap Quote[/bold cyan]")
        
        try:
            # Create swap request
            request = OdosSwapRequest(
                user_address=self.wallet_address,
                from_token="ETH",  # Using symbol for readability
                to_token="USDC",
                amount="1000000000000000000",  # 1 ETH in wei
                slippage=0.5,  # 0.5% slippage
                chain_id=1  # Ethereum
            )
            
            with Progress() as progress:
                task = progress.add_task("[green]Getting quote...", total=1)
                
                # Get the swap quote
                swap_details = await self.odos_service.get_swap_quote(request)
                progress.update(task, completed=1)
                
                if "error" in swap_details:
                    console.print(f"[red]Error: {swap_details['error']}[/red]")
                    return
                
                # Display the quote in a nice panel
                panel_content = f"""
                [bold cyan]Swap Details[/bold cyan]
                
                [green]From:[/green] {swap_details['from_token'].get('symbol', 'Unknown')} ({swap_details['from_token'].get('name', 'Unknown')})
                [green]To:[/green] {swap_details['to_token'].get('symbol', 'Unknown')} ({swap_details['to_token'].get('name', 'Unknown')})
                
                [green]Amount In:[/green] {self._format_amount(swap_details['quote']['input_token']['amount'], swap_details['from_token'].get('decimals', 18))} {swap_details['from_token'].get('symbol', 'Token')}
                [green]Amount Out:[/green] {self._format_amount(swap_details['estimated_output'], swap_details['to_token'].get('decimals', 18))} {swap_details['to_token'].get('symbol', 'Token')}
                
                [green]Price Impact:[/green] {swap_details['price_impact_percentage']:.4f}%
                [green]Gas Estimate:[/green] {self._format_gas(swap_details['quote']['gas_estimate_wei'])}
                [green]Path ID:[/green] {swap_details['quote']['path_id']}
                
                [bold yellow]Risk Assessment:[/bold yellow]
                [yellow]Risk Level:[/yellow] {swap_details['risk_assessment'].get('risk_level', 'Unknown')}
                """
                
                console.print(Panel(panel_content, title="Swap Quote", expand=False))
                
        except Exception as e:
            logger.error(f"Error in token swap quote demo: {str(e)}")
            console.print(f"[red]Error: {str(e)}[/red]")
            
    async def demo_routing_visualization(self):
        """Demo visualization of swap routing"""
        console.print("\n[bold cyan]Visualizing Swap Routing[/bold cyan]")
        
        try:
            # Create swap request for a more complex swap
            request = OdosSwapRequest(
                user_address=self.wallet_address,
                from_token="ETH",
                to_token="DAI",
                amount="1000000000000000000",  # 1 ETH in wei
                slippage=0.5,
                chain_id=1  # Ethereum
            )
            
            with Progress() as progress:
                task = progress.add_task("[green]Getting routes...", total=1)
                
                # Get the swap routes
                routes = await self.odos_service.get_swap_routes(request)
                progress.update(task, completed=1)
                
                if "error" in routes:
                    console.print(f"[red]Error: {routes['error']}[/red]")
                    return
                
                # Display a table of routes
                table = Table(title=f"Route from {routes['from_token'].get('symbol', 'Token')} to {routes['to_token'].get('symbol', 'Token')}")
                table.add_column("Step", style="cyan")
                table.add_column("Protocol", style="green")
                table.add_column("Portion", style="yellow")
                table.add_column("From", style="blue")
                table.add_column("To", style="blue")
                
                # Add route steps
                for i, step in enumerate(routes["route"], 1):
                    table.add_row(
                        str(i),
                        step.get("protocol", "Unknown"),
                        f"{step.get('portion', 0)}%",
                        step.get("from_token", "Unknown"),
                        step.get("to_token", "Unknown")
                    )
                    
                console.print(table)
                
                # Display a summary
                panel_content = f"""
                [bold cyan]Routing Summary[/bold cyan]
                
                Odos optimizes your swap by finding the most efficient path through various liquidity sources.
                
                [green]Amount In:[/green] {self._format_amount(routes['amount_in'], routes['from_token'].get('decimals', 18))} {routes['from_token'].get('symbol', 'Token')}
                [green]Amount Out:[/green] {self._format_amount(routes['amount_out'], routes['to_token'].get('decimals', 18))} {routes['to_token'].get('symbol', 'Token')}
                
                [green]Price Impact:[/green] {routes['price_impact']:.4f}%
                [green]Gas Estimate:[/green] {self._format_gas(routes['gas_estimate'])}
                """
                
                console.print(Panel(panel_content, title="Routing Summary", expand=False))
                
        except Exception as e:
            logger.error(f"Error in routing visualization demo: {str(e)}")
            console.print(f"[red]Error: {str(e)}[/red]")
            
    async def demo_multi_token_swap(self):
        """Demo a more complex swap scenario"""
        console.print("\n[bold cyan]Multi-Token Swap Scenario[/bold cyan]")
        
        # This would be a more complex example like splitting funds across multiple tokens
        # or showing how Odos can optimize gas across multiple swaps
        console.print(Panel(
            "This feature would demonstrate how Odos can optimize a complex swap involving multiple tokens or splitting "
            "funds across different tokens.\n\n"
            "For production implementation, this would utilize advanced Odos features such as batch transactions "
            "or split routes optimization.",
            title="Advanced Swap Optimization",
            expand=False
        ))
    
    def _format_amount(self, amount_str: str, decimals: int = 18) -> str:
        """Format token amount with proper decimal places"""
        try:
            # Convert from smallest units to token units
            amount = float(amount_str) / (10 ** decimals)
            if amount >= 1:
                return f"{amount:.4f}"
            elif amount >= 0.0001:
                return f"{amount:.6f}"
            else:
                return f"{amount:.8f}"
        except Exception:
            return amount_str
            
    def _format_gas(self, gas_wei: str) -> str:
        """Format gas in a readable way"""
        try:
            gas = int(gas_wei)
            # Convert to Gwei
            gas_gwei = gas / 1e9
            return f"{gas_gwei:.2f} Gwei (approx. {gas} wei)"
        except Exception:
            return gas_wei

async def main():
    """Run the demos"""
    console.print(Panel.fit(
        "[bold green]Odos Protocol Integration Demo[/bold green]\n"
        "[blue]Showcasing optimal DeFi swaps and routing[/blue]",
        style="cyan"
    ))
    
    demo = OdosDemo()
    
    try:
        # Load environment
        console.print("\n[magenta]Environment:[/magenta]")
        console.print(f"Wallet Address: {demo.wallet_address}")
        console.print(f"Using Odos API key: {'Yes' if os.getenv('ODOS_API_KEY') else 'No'}")
        
        # Run the demos
        await demo.demo_supported_tokens()
        await demo.demo_token_swap_quote()
        await demo.demo_routing_visualization()
        await demo.demo_multi_token_swap()
        
    except Exception as e:
        logger.error(f"Error in demo: {str(e)}")
        console.print(f"[red]Error running demo: {str(e)}[/red]")
        
    finally:
        await demo.close()
        console.print("\n[bold green]Demo completed![/bold green]")

if __name__ == "__main__":
    asyncio.run(main()) 