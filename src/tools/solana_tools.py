import yfinance as yf
import pandas as pd
from crewai import Agent, Crew, Task, Process
from crewai.tools import BaseTool
import numpy as np
from pydantic import BaseModel, Field, ConfigDict
from typing import Type, Optional
from solana.rpc.api import Client
from solders.pubkey import Pubkey
import requests


SOLANA_RPC="https://mainnet.helius-rpc.com/?api-key=d4153e53-a035-42f8-a25f-a10ecbea0704"

class TokenSchema(BaseModel):
    token_address: str = Field(..., description="Solana token address")


class TokenFundamentalAnalysis(BaseTool):
    name: str = "Analyze token fundamentals"
    description: str = "A tool to analyze Solana token fundamentals"
    args_schema: Type[BaseModel] = TokenSchema
    result_as_answer: bool = True
    model_config = ConfigDict(arbitrary_types_allowed=True)
    client: Optional[Client] = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.client = Client(SOLANA_RPC)

    def _run(self, **kwargs):
        token_address = kwargs["token_address"]
        
        # Get token info from Jupiter API
        jupiter_response = requests.get(f"https://price.jup.ag/v4/price?ids={token_address}")
        token_data = jupiter_response.json()["data"][token_address]

        # Get additional token metrics from Solana RPC
        token_supply = self.client.get_token_supply(Pubkey.from_string(token_address))
        
        fundamental_analysis = {
            "Price (USDC)": token_data.get("price", "N/A"),
            "24h Volume": token_data.get("volume24h", "N/A"),
            "Market Cap": token_data.get("marketCap", "N/A"),
            "Total Supply": token_supply.value.ui_amount if token_supply else "N/A",
            "Price Change 24h": f"{token_data.get('priceChange24h', 0) * 100:.2f}%",
        }

        return fundamental_analysis


class TokenTechnicalAnalysis(BaseTool):
    name: str = "Analyze token technicals"
    description: str = "A tool for technical analysis of Solana tokens"
    args_schema: Type[BaseModel] = TokenSchema
    model_config = ConfigDict(arbitrary_types_allowed=True)
    client: Optional[Client] = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.client = Client(SOLANA_RPC)

    def _run(self, **kwargs):
        token_address = kwargs["token_address"]
        
        # Get network stats
        network_stats = self.client.get_recent_performance_samples()
        
        # Calculate network metrics
        if network_stats:
            avg_tps = sum(stat.num_transactions for stat in network_stats) / len(network_stats)
            avg_slots = sum(stat.num_slots for stat in network_stats) / len(network_stats)
        else:
            avg_tps = "N/A"
            avg_slots = "N/A"

        technical_analysis = {
            "Average TPS": avg_tps,
            "Average Slots": avg_slots,
            "Network Health": "Good" if avg_tps > 2000 else "Moderate",
        }

        return technical_analysis


class TokenInfoTool(BaseTool):
    name: str = "Get token information"
    description: str = "A tool to get detailed information about a Solana token"
    args_schema: Type[BaseModel] = TokenSchema
    model_config = ConfigDict(arbitrary_types_allowed=True)
    client: Optional[Client] = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.client = Client(SOLANA_RPC)

    def _run(self, **kwargs):
        token_address = kwargs["token_address"]
        
        # Get token metadata from Solana token list
        token_list_url = "https://raw.githubusercontent.com/solana-labs/token-list/main/src/tokens/solana.tokenlist.json"
        response = requests.get(token_list_url)
        token_list = response.json()
        
        token_info = next(
            (token for token in token_list["tokens"] if token["address"] == token_address),
            None
        )
        
        if token_info:
            return {
                "Name": token_info.get("name", "N/A"),
                "Symbol": token_info.get("symbol", "N/A"),
                "Decimals": token_info.get("decimals", "N/A"),
                "Tags": token_info.get("tags", []),
                "Website": token_info.get("website", "N/A"),
                "Twitter": token_info.get("twitter", "N/A"),
            }
        else:
            return {"error": "Token not found in Solana token list"} 