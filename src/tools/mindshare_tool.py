from typing import Type
from pydantic import BaseModel, Field
from crewai.tools import BaseTool
from supabase import create_client, Client
from datetime import datetime, timedelta
import os

class MindshareSchema(BaseModel):
    token_symbol: str = Field(
        ..., description="Name of token for fetching mindshare analysis"
    )
    hours: int = Field(
        24, description="Number of hours of data to analyze"
    )

class MindshareTool(BaseTool):
    """
    A tool for analyzing token mindshare data from Supabase.
    
    This tool fetches and analyzes token performance data including:
    - Market metrics (price, volume, RSI, MACD)
    - Social metrics (engagement, sentiment, viral score)
    - Combined signals (mindshare score, buy/sell zones)
    
    Example:
        tool = MindshareTool()
        result = tool.run(token_symbol="BTC", hours=24)
    """
    
    name: str = "Fetch mindshare data for a token"
    description: str = "A tool to fetch mindshare and market data including social metrics, price action, and technical indicators"
    args_schema: Type[BaseModel] = MindshareSchema
    supabase_client: Client = None

    model_config = {"arbitrary_types_allowed": True}

    def __init__(self):
        super().__init__()
        # Initialize Supabase client
        self.supabase_client = create_client(
            os.environ["SUPABASE_URL"],
            os.environ["SUPABASE_KEY"]
        )

    def _run(self, **kwargs):
        token_symbol = kwargs["token_symbol"]
        hours = kwargs.get("hours", 24)
        
        # Calculate the timestamp for hours ago
        time_threshold = (datetime.now() - timedelta(hours=hours)).isoformat()
        
        # Fetch latest data from Supabase
        response = (
            self.supabase_client.table("mindshare_analysis")
            .select("""
                token_symbol,
                timestamp,
                price,
                volume,
                market_cap,
                rsi,
                macd,
                macd_signal,
                macd_hist,
                price_change_24h,
                engagement,
                sentiment,
                mindshare_index,
                social_momentum,
                mindshare_strength,
                social_score,
                market_score,
                mindshare_score,
                buy_zone,
                sell_zone,
                viral_score,
                sentiment_price_divergence,
                combined_momentum
            """)
            .eq("token_symbol", token_symbol)
            .gte("timestamp", time_threshold)
            .order("timestamp", desc=True)
            .execute()
        )
        
        if not response.data:
            return {"error": f"No data found for token {token_symbol}"}
        
        # Get the latest record
        latest = response.data[0]
        
        # Calculate some aggregated metrics
        data = response.data
        return {
            "latest": latest,
            "summary": {
                "avg_sentiment": sum(d["sentiment"] for d in data if d["sentiment"]) / len(data),
                "avg_engagement": sum(d["engagement"] for d in data if d["engagement"]) / len(data),
                "avg_mindshare": sum(d["mindshare_score"] for d in data if d["mindshare_score"]) / len(data),
                "price_change": latest["price_change_24h"],
                "social_momentum": latest["social_momentum"],
                "viral_score": latest["viral_score"],
                "market_score": latest["market_score"],
                "mindshare_strength": latest["mindshare_strength"],
                "buy_zone": latest["buy_zone"],
                "sell_zone": latest["sell_zone"]
            }
        }

    @property
    def tool_description(self) -> str:
        return """
        Tool for analyzing token mindshare and market data.
        
        Capabilities:
        - Fetches real-time market data (price, volume, RSI, MACD)
        - Analyzes social metrics (engagement, sentiment, viral score)
        - Provides combined signals (mindshare score, buy/sell zones)
        - Calculates technical indicators and momentum
        
        Input Parameters:
        - token_symbol: The token to analyze (e.g., "BTC", "ETH")
        - hours: Number of hours of historical data to analyze (default: 24)
        
        Example Usage:
        ```python
        result = tool.run(token_symbol="BTC", hours=24)
        print(f"Current price: ${result['latest']['price']}")
        print(f"Buy zone: {result['summary']['buy_zone']}")
        ```
        """