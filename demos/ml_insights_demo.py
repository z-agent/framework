"""
Advanced ML Trading Insights Demo
Demonstrates real-world examples of how ML enhances crypto trading decisions
"""

import asyncio
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from datetime import datetime
import json
from typing import List, Dict, Any
import logging

from src.core.enhanced_trading_strategy import EnhancedTradingStrategy
from src.core.market_data import MarketDataService
from src.core.llm_intent_service import LLMIntentService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
console = Console()

class MLInsightsDemo:
    def __init__(self):
        """Initialize ML Insights Demo with enhanced trading strategy"""
        self.strategy = EnhancedTradingStrategy()
        self.nlp_service = LLMIntentService()
        
    async def _fetch_token_data(self, token: str) -> Dict[str, Any]:
        """Fetch comprehensive token data with error handling"""
        try:
            data = await self.strategy.market_data.get_token_data(token)
            if not data:
                logger.warning(f"No data available for {token}, using fallback values")
                return self._get_fallback_data()
            return data
        except Exception as e:
            logger.error(f"Error fetching data for {token}: {str(e)}")
            return self._get_fallback_data()

    def _get_fallback_data(self) -> Dict[str, Any]:
        """Provide fallback data for error cases"""
        return {
            "price": 0.0,
            "volume": 0.0,
            "market_cap": 0.0,
            "price_change_24h": 0.0,
            "rsi": 50.0,
            "volatility": 0.0
        }

    async def show_market_comparison(self, tokens: List[str]):
        """Display comprehensive market comparison with trader insights"""
        console.print("\nAnalyzing tokens:", ", ".join(tokens))
        
        # Create comparison table
        table = Table(title="Token Market Comparison")
        table.add_column("Metric", style="cyan")
        for token in tokens:
            table.add_column(token, style="yellow")
            
        # Fetch and display data for each token
        metrics = {}
        for token in tokens:
            data = await self._fetch_token_data(token)
            predictions = self._get_ml_predictions(data)
            metrics[token] = {
                "Price": f"${data.get('price', 0):.4f}",
                "24h Change": f"{data.get('price_change_24h', 0):.2f}%",
                "Volume": f"${data.get('volume', 0):,.2f}",
                "Market Cap": f"${data.get('market_cap', 0):,.2f}",
                "RSI": f"{data.get('rsi', 0):.2f}",
                "Volatility": f"{data.get('volatility', 0):.2f}%",
                "Social Score": f"{data.get('social_score', 0):.2f}",
                "Market Score": f"{data.get('market_score', 0):.2f}",
                "Mindshare Score": f"{data.get('mindshare_score', 0):.2f}",
                "ML Price Direction": predictions.get('price', {}).get('direction', 'neutral'),
                "ML Risk Score": f"{predictions.get('risk', {}).get('risk_score', 0.5)*100:.2f}%",
                "Market Impact": f"{data.get('market_impact', 0.5)*100:.2f}%"
            }
            
        # Add rows to table
        for metric in metrics[tokens[0]].keys():
            row = [metric]
            for token in tokens:
                row.append(metrics[token][metric])
            table.add_row(*row)
            
        console.print(table)
        
        # Display relative strength analysis
        console.print("\n💪 Relative Strength Analysis")
        for token in tokens:
            data = await self._fetch_token_data(token)
            predictions = self._get_ml_predictions(data)
            strength_score = self._calculate_relative_strength(data, predictions)
            ranking = self._get_strength_ranking(strength_score)
            
            console.print(Panel(
                f"{token}\n"
                f"Strength Score: {strength_score*100:.2f}%\n"
                f"Ranking: {ranking}",
                expand=False
            ))

    def _calculate_relative_strength(self, data: Dict[str, Any], predictions: Dict[str, Any]) -> float:
        """Calculate relative strength score based on multiple factors"""
        try:
            # Get values with defaults
            price_momentum = float(data.get('price_momentum', 0)) / 100
            volume_momentum = float(data.get('volume_momentum', 0)) / 100
            rsi = float(data.get('rsi', 50))
            market_impact = float(data.get('market_impact', 0.5))  # Get market impact directly from data
            
            # Get ML predictions with defaults
            price_pred = predictions.get('price', {})
            risk_pred = predictions.get('risk', {})
            
            factors = {
                'price_momentum': price_momentum,
                'volume_strength': volume_momentum,
                'rsi_strength': (rsi - 30) / 40,  # Normalize RSI
                'ml_confidence': float(price_pred.get('confidence', 0.5)),
                'risk_score': 1 - float(risk_pred.get('risk_score', 0.5)),  # Inverse risk
                'market_impact': 1 - market_impact  # Lower impact is better
            }
            
            weights = {
                'price_momentum': 0.25,
                'volume_strength': 0.15,
                'rsi_strength': 0.15,
                'ml_confidence': 0.20,
                'risk_score': 0.15,
                'market_impact': 0.10
            }
            
            score = sum(
                min(max(v, 0), 1) * weights[k]
                for k, v in factors.items()
            )
            
            return min(max(score, 0), 1)
            
        except Exception as e:
            logger.error(f"Error calculating relative strength: {str(e)}")
            return 0.5  # Return neutral score on error

    def _get_strength_ranking(self, score: float) -> str:
        """Convert strength score to ranking"""
        if score >= 0.8:
            return "Very Strong 🚀"
        elif score >= 0.6:
            return "Strong 💪"
        elif score >= 0.4:
            return "Neutral ⚖️"
        elif score >= 0.2:
            return "Weak 🔻"
        else:
            return "Very Weak ⚠️"

    async def show_real_world_example(self, token_symbol: str, scenario_name: str, scenario_description: str):
        """Display real-world trading example with ML insights and trader interpretation"""
        console.print(Panel(f"[bold blue]📊 {scenario_name}[/bold blue]", style="blue"))
        console.print(f"[italic]{scenario_description}[/italic]\n")

        try:
            # Get token data and ML predictions
            token_data = await self._fetch_token_data(token_symbol)
            if not token_data:
                console.print(f"[red]No data available for {token_symbol}[/red]")
                return
            
            ml_predictions = self._get_ml_predictions(token_data)
            insights = self.strategy._generate_actionable_insights(token_data, ml_predictions)
            
            # Display analysis sections
            self._display_market_context(token_data)
            self._display_ml_insights(ml_predictions, insights)
            self._display_trading_recommendations(insights)
            self._display_risk_analysis(insights)
            
            # Add trader interpretation
            self._display_trader_interpretation(token_data, ml_predictions, insights)
            
        except Exception as e:
            logger.error(f"Error processing {token_symbol}: {str(e)}")
            console.print(f"Error processing {token_symbol}: {str(e)}")

    def _display_market_context(self, token_data: dict):
        """Display market context in a clean format"""
        table = Table(title="📈 Market Context")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="yellow")
        
        metrics = {
            "Price": f"${token_data.get('price', 0):.4f}",
            "24h Volume": f"${token_data.get('volume', 0):,.2f}",
            "Market Cap": f"${token_data.get('market_cap', 0):,.2f}",
            "24h Change": f"{token_data.get('price_change_24h', 0):.2f}%",
            "RSI": f"{token_data.get('rsi', 0):.2f}",
            "Volatility": f"{token_data.get('volatility', 0):.2%}",
            "Social Score": f"{token_data.get('social_score', 0):.2f}",
            "Market Score": f"{token_data.get('market_score', 0):.2f}",
            "Mindshare Score": f"{token_data.get('mindshare_score', 0):.2f}",
            "Market Impact": f"{token_data.get('market_impact', 0.5)*100:.2f}%"
        }
        
        for metric, value in metrics.items():
            table.add_row(metric, value)
        
        console.print(table)

    def _display_ml_insights(self, ml_predictions: dict, insights: dict):
        """Display ML-driven insights"""
        console.print("\n[bold]🤖 ML-Enhanced Analysis[/bold]")
        
        # Price Prediction
        price_pred = ml_predictions.get("price", {})
        console.print(Panel(
            f"Direction: {price_pred.get('direction', 'neutral').upper()}\n"
            f"Magnitude: {price_pred.get('magnitude', 0):.1%}\n"
            f"Confidence: {price_pred.get('confidence', 0):.1%}",
            title="Price Prediction",
            style="green" if price_pred.get('direction') == "up" else "red"
        ))

        # Risk Analysis
        risk_pred = ml_predictions.get("risk", {})
        impact_pred = ml_predictions.get("impact", {})
        
        console.print(Panel(
            f"Risk Score: {risk_pred.get('risk_score', 0.5)*100:.1f}%\n"
            f"Volume Impact: {impact_pred.get('volume_factor', 0)*100:.1f}%\n"
            f"Liquidity Impact: {impact_pred.get('liquidity_factor', 0)*100:.1f}%\n"
            f"Volatility Impact: {impact_pred.get('volatility_factor', 0)*100:.1f}%",
            title="Risk Analysis",
            style="yellow"
        ))

        # Trading Opportunities
        if insights.get("trading_opportunities"):
            for opp in insights["trading_opportunities"]:
                console.print(Panel(
                    f"Type: {opp.get('type', 'unknown').upper()}\n"
                    f"Timeframe: {opp.get('timeframe', 'unknown')}\n"
                    f"Size: {opp.get('size', 'unknown')}\n"
                    f"Confidence: {opp.get('confidence', '0%')}",
                    title="Trading Opportunity",
                    style="green"
                ))

    def _display_trading_recommendations(self, insights: dict):
        """Display trading recommendations"""
        if insights.get("entry_points"):
            console.print("\n[bold]📍 Entry Points[/bold]")
            for entry in insights["entry_points"]:
                console.print(Panel(
                    f"Type: {entry.get('type', 'unknown').upper()}\n"
                    f"Price: {entry.get('price', '$0.00')}\n"
                    f"Strength: {entry.get('strength', 'unknown')}",
                    style="blue"
                ))

        if insights.get("risk_factors", {}).get("key_factors"):
            console.print("\n[bold]⚠️ Risk Factors[/bold]")
            for factor in insights["risk_factors"]["key_factors"]:
                console.print(Panel(
                    f"Factor: {factor.get('factor', 'unknown')}\n"
                    f"Level: {factor.get('level', 'unknown')}\n"
                    f"Action: {factor.get('action', 'unknown')}",
                    style="red"
                ))

    def _display_risk_analysis(self, insights: dict):
        """Display risk analysis"""
        console.print("\n[bold]⚠️ Risk Analysis[/bold]")
        
        risk_factors = insights.get("risk_factors", {})
        if risk_factors:
            table = Table(title="Risk Factors")
            table.add_column("Factor", style="cyan")
            table.add_column("Level", style="yellow")
            table.add_column("Recommended Action", style="green")
            
            for factor in risk_factors.get("key_factors", []):
                table.add_row(
                    factor["factor"],
                    factor["level"].upper(),
                    factor["action"]
                )
            console.print(table)

    def _display_trader_interpretation(self, token_data: dict, ml_predictions: dict, insights: dict):
        """Display trader-friendly interpretation"""
        console.print("\n[bold]💡 Trader's Interpretation[/bold]")
        
        # Market Context
        buy_pressure = token_data.get('buy_pressure', 0)
        sell_pressure = token_data.get('sell_pressure', 0)
        total_pressure = buy_pressure + sell_pressure
        pressure_ratio = buy_pressure / total_pressure if total_pressure > 0 else 0.5
        
        market_status = Panel(
            f"Buy Pressure: {buy_pressure:,.2f}\n"
            f"Sell Pressure: {sell_pressure:,.2f}\n"
            f"Pressure Ratio: {pressure_ratio:.3f}\n"
            f"Market Impact: {token_data.get('market_impact', 0.5)*100:.2f}%",
            title="Market Status",
            style="cyan"
        )
        console.print(market_status)
        
        # Trading Signals
        signals = insights.get("market_sentiment", {})
        signals_panel = Panel(
            f"Overall: {signals.get('overall', 'neutral').upper()}\n"
            f"Social Momentum: {signals.get('social_momentum', 0):.2f}\n"
            f"Engagement Trend: {signals.get('engagement_trend', 'stable')}\n"
            f"Confidence: {signals.get('confidence', '0%')}",
            title="Trading Signals",
            style="magenta"
        )
        console.print(signals_panel)

    async def process_nlp_command(self, command: str) -> Dict[str, Any]:
        """Process natural language trading command"""
        try:
            # Analyze intent using NLP service
            intent = await self.nlp_service.analyze_intent(command)
            
            # Get token data and ML insights
            if 'token' in intent.parameters:
                token = intent.parameters['token'].value
                data = await self._fetch_token_data(token)
                predictions = self._get_ml_predictions(data)
                insights = self.strategy._generate_actionable_insights(data, predictions)
                
                return {
                    "intent": intent.dict(),
                    "market_data": data,
                    "ml_predictions": predictions,
                    "insights": insights,
                    "interpretation": self._generate_nlp_response(intent, predictions, insights)
                }
            
            return {"error": "No token specified in command"}
            
        except Exception as e:
            logger.error(f"Error processing NLP command: {str(e)}")
            return {"error": str(e)}

    def _generate_nlp_response(self, intent: Any, predictions: Dict[str, Any], insights: Dict[str, Any]) -> str:
        """Generate natural language response based on analysis"""
        if intent.category == "trade":
            return self._generate_trade_response(intent, predictions, insights)
        elif intent.category == "analysis":
            return self._generate_analysis_response(predictions, insights)
        else:
            return "I understand your request but need more specific trading-related information."

    def _generate_trade_response(self, intent: Any, predictions: Dict[str, Any], insights: Dict[str, Any]) -> str:
        """Generate trading-focused response"""
        response = []
        
        # Add market context
        response.append(f"Based on my analysis of {intent.parameters['token'].value}:")
        
        # Add ML predictions
        price_pred = predictions.get('price', {})
        response.append(f"• Price is likely moving {price_pred.get('direction', 'neutral')} "
                      f"with {price_pred.get('confidence', 0)*100:.1f}% confidence")
        
        # Add risk assessment
        risk = predictions.get('risk', {}).get('risk_score', 0)
        response.append(f"• Current risk level is {risk*100:.1f}%")
        
        # Add recommendations
        if 'recommendations' in insights:
            response.append("\nRecommended Actions:")
            for rec in insights['recommendations']:
                response.append(f"• {rec}")
                
        return "\n".join(response)

    def _generate_analysis_response(self, predictions: Dict[str, Any], insights: Dict[str, Any]) -> str:
        """Generate analysis-focused response"""
        response = []
        
        # Add market analysis
        response.append("Market Analysis:")
        response.append(f"• ML Price Direction: {predictions.get('price', {}).get('direction', 'neutral')}")
        response.append(f"• Risk Level: {predictions.get('risk', {}).get('risk_score', 0)*100:.1f}%")
        response.append(f"• Market Impact: {predictions.get('impact', {}).get('impact_score', 0)*100:.1f}%")
        
        # Add key insights
        if 'key_points' in insights:
            response.append("\nKey Insights:")
            for point in insights['key_points']:
                response.append(f"• {point}")
                
        return "\n".join(response)

    def _get_ml_predictions(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Get ML predictions for token data"""
        try:
            return {
                "price": self.strategy._predict_price_movement(data),
                "risk": self.strategy._predict_risk_level(data),
                "impact": self.strategy._predict_market_impact(data)
            }
        except Exception as e:
            logger.error(f"Error getting ML predictions: {str(e)}")
            return {
                "price": {"direction": "neutral", "magnitude": 0.0, "confidence": 0.0},
                "risk": {"risk_score": 0.5, "confidence": 0.0},
                "impact": {"impact_score": 0.5, "volume_factor": 0.0, "liquidity_factor": 0.0, "volatility_factor": 0.0}
            }

async def run_demo():
    """Run the ML insights demo with real-world examples"""
    demo = MLInsightsDemo()
    
    console.print(Panel.fit(
        "[bold magenta]🚀 Advanced ML Trading Insights Demo[/bold magenta]\n"
        "Real-world examples of how ML enhances trading decisions",
        style="magenta"
    ))

    # Market Comparison
    tokens_to_analyze = ["SOL", "JTO", "BONK", "APES"]
    console.print(f"\n[bold]Analyzing tokens: {', '.join(tokens_to_analyze)}[/bold]")
    await demo.show_market_comparison(tokens_to_analyze)

    # Individual Token Analysis
    tokens = [
        ("SOL", "SOL Technical Analysis", "ML-enhanced technical analysis with breakout detection"),
        ("JTO", "JTO Risk Analysis", "Deep dive into risk factors and market impact"),
        ("BONK", "BONK Sentiment Analysis", "Social sentiment and market momentum analysis"),
        ("APES", "APES Momentum Analysis", "Detailed momentum and trend analysis")
    ]

    for token, name, desc in tokens:
        console.print(f"\n[bold]Analyzing {token}...[/bold]")
        await demo.show_real_world_example(token, name, desc)

    # Summary of Benefits
    # console.print(Panel(
    #     "[bold green]Why ML-Enhanced Trading Makes a Difference[/bold green]\n\n"
    #     "1. [bold]Smarter Signal Detection[/bold]\n"
    #     "   • Reduces false positives by 60%\n"
    #     "   • Multi-factor confirmation\n"
    #     "   • Confidence-weighted decisions\n\n"
    #     "2. [bold]Advanced Risk Management[/bold]\n"
    #     "   • Real-time risk scoring\n"
    #     "   • Market impact prediction\n"
    #     "   • Dynamic position sizing\n\n"
    #     "3. [bold]Market Sentiment Edge[/bold]\n"
    #     "   • Social momentum analysis\n"
    #     "   • Engagement tracking\n"
    #     "   • Sentiment-price correlation\n\n"
    #     "4. [bold]Execution Intelligence[/bold]\n"
    #     "   • Optimal entry points\n"
    #     "   • Liquidity analysis\n"
    #     "   • Smart sizing recommendations\n",
    #     title="🎯 Key Benefits",
    #     style="green"
    # ))

if __name__ == "__main__":
    console.print("\n[bold]🚀 Starting ML Trading Insights Demo...[/bold]\n")
    asyncio.run(run_demo()) 