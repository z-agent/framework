import requests
import os
import pandas as pd
import asyncio
import concurrent.futures
from crewai.tools import BaseTool
# from crewai_tools import SerperDevTool  # Commented out due to import issues
from pydantic import BaseModel, Field
from typing import Type, Optional
from src.vendor.ivishx.data_sources import CoinGeckoClient
from src.vendor.ivishx.strategy import IvishXAnalyzer

# Using SerperDevTool for Twitter sentiment as suggested.
# You will need to set the SERPER_API_KEY environment variable.
# twitter_sentiment_tool = SerperDevTool(name="TwitterSentiment", description="Search Twitter for coin sentiment")  # Commented out

class CoinSchema(BaseModel):
    coin: str = Field(..., description="The symbol or mint address of the coin, e.g., 'TOSHI'")

class PumpFunVolumeTool(BaseTool):
    name: str = "PumpFunVolume"
    description: str = "Get current trading volume of a coin on Pump.fun by its mint address."
    args_schema: Type[BaseModel] = CoinSchema

    def _run(self, coin: str) -> str:
        """
        Fetches trading data from the PumpPortal API to calculate recent volume.
        'coin' should be the token's mint address.
        """
        try:
            # Note: PumpPortal doesn't have a direct volume endpoint.
            # We're checking for recent trades as a proxy for activity.
            # A more advanced implementation could use websockets to track live volume.
            url = f"https://pumpportal.fun/api/data/trades/{coin}" # This is a hypothetical endpoint, docs show websockets
            # Since  there's no direct REST endpoint for volume, we'll simulate a call and return a semi-static message.
            # A real implementation would connect to 'wss://pumpportal.fun/api/data' and subscribe to trades.
            
            # For the demo, we'll check if the token exists via SolanaTracker as a proxy.
            solana_tracker_url = f"https://data.solanatracker.io/tokens/{coin}"
            headers = {"x-api-key": os.environ["SOLANA_TRACKER_API_KEY"]}
            response = requests.get(solana_tracker_url, headers=headers)
            response.raise_for_status()
            data = response.json()

            if data and data.get('pools'):
                pool_data = data['pools'][0] # Get first pool
                volume_24h = pool_data.get('txns', {}).get('volume', 'not available')
                return f"Token found. 24h trade volume is {volume_24h}."

            return "[PUMP.FUN] No recent trading activity found for this token."
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                return f"[PUMP.FUN] Token with mint address '{coin}' not found."
            return f"[PUMP.FUN] Error fetching data: {e}"
        except Exception as e:
            return f"[PUMP.FUN] An unexpected error occurred: {e}"


class WhaleTrackerTool(BaseTool):
    name: str = "WhaleActivityCheck"
    description: str = "Detect large wallet trades for a given coin using its mint address."
    args_schema: Type[BaseModel] = CoinSchema

    def _run(self, coin: str, whale_threshold_usd: int = 10000) -> str:
        """
        Fetches recent trades from the Solana Tracker API and identifies large 'whale' transactions.
        'coin' should be the token's mint address.
        """
        try:
            url = f"https://data.solanatracker.io/trades/{coin}"
            headers = {"x-api-key": os.environ["SOLANA_TRACKER_API_KEY"]}
            params = {'limit': 100} # Check last 100 trades
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            trades = response.json().get('trades', [])

            whale_trades = []
            for trade in trades:
                if trade.get('volume', 0) > whale_threshold_usd:
                    whale_trades.append(
                        f"- A trade of ${trade['volume']:.2f} was made by {trade['wallet']} ({trade['type']})"
                    )

            if not whale_trades:
                return f"No whale activity (trades > ${whale_threshold_usd}) found in the last 100 transactions for {coin}."

            return f"Found {len(whale_trades)} whale trade(s) for {coin} in the last 100 transactions:\n" + "\n".join(whale_trades)
        except requests.exceptions.HTTPError as e:
             if e.response.status_code == 404:
                return f"[WHALE] Token with mint address '{coin}' not found on Solana Tracker."
             return f"[WHALE] Error fetching data: {e}"
        except Exception as e:
            return f"[WHALE] An unexpected error occurred: {e}"


# Instantiate the tools
pumpfun_volume_tool = PumpFunVolumeTool()
whale_tracker_tool = WhaleTrackerTool() 


class IvishXArgs(BaseModel):
    symbol: str = Field(..., description="CoinGecko id or symbol, e.g., 'bitcoin', 'eth', 'sol'")
    days: int = Field(30, description="Number of days for OHLC data (default 30)")


class IvishXAnalyzeTool(BaseTool):
    name: str = "IvishXAnalyze"
    description: str = "Run ivishX analyzer (EMA/Fib/RSI/MACD + structure) using built-in vendorized code."
    args_schema: Type[BaseModel] = IvishXArgs

    def _run(self, symbol: str, days: int = 30) -> dict:
        print(f"Running IvishX analysis for {symbol} with {days} days")
        try:
            cg = CoinGeckoClient()
            df = cg.ohlc(symbol, days=days)
            analyzer = IvishXAnalyzer()
            analysis = analyzer.analyze(df)
            
            # Format for frontend integration - flatten the structure
            signal = analysis['signal']
            confluence = analysis['confluence']
            structure = analysis['structure']
            
            # Add full OHLC data for charting
            ohlc_data = []
            for _, row in df.iterrows():
                ohlc_data.append({
                    "timestamp": row['timestamp'].isoformat() if hasattr(row['timestamp'], 'isoformat') else str(row['timestamp']),
                    "open": float(row['open']),
                    "high": float(row['high']),
                    "low": float(row['low']),
                    "close": float(row['close']),
                    "volume": float(row['volume']) if 'volume' in row and pd.notna(row['volume']) else 0.0
                })
            
            # Ensure all required fields exist and have proper types
            signal_type = signal.get('type', 'WAIT')
            confidence = int(signal.get('confidence', 0))
            entry = float(signal.get('entry', 0.0))
            stop_loss = float(signal.get('stop_loss', 0.0))
            tp1 = float(signal.get('tp1', 0.0))
            tp2 = float(signal.get('tp2', 0.0))
            rr = float(signal.get('rr', 0.0))
            reasons = signal.get('reasons', [])
            
            # Ensure confluence data exists
            price = float(confluence.get('price', 0.0))
            rsi = float(confluence.get('rsi', 50.0))
            macd = float(confluence.get('macd', 0.0))
            macd_signal = float(confluence.get('macd_signal', 0.0))
            ema_data = confluence.get('ema', (0.0, 0.0, 0.0, 0.0, 0.0))
            fib50 = float(confluence.get('fib50', 0.0))
            fib618 = float(confluence.get('fib618', 0.0))
            long_score = int(confluence.get('long', {}).get('score', 0))
            short_score = int(confluence.get('short', {}).get('score', 0))
            
            # Ensure structure data exists
            structure_trend = structure.get('structure_trend', 'NEUTRAL')
            swing_highs = structure.get('swing_highs', [])
            swing_lows = structure.get('swing_lows', [])
            bos_signals = structure.get('bos_signals', [])
            choch_signals = structure.get('choch_signals', [])
            
            # Create trading signal response that matches frontend expectations
            result = {
                "success": True,
                "symbol": symbol,
                "signal": {
                    "type": signal_type,
                    "confidence": confidence,
                    "entry": entry,
                    "stop_loss": stop_loss,
                    "stopLoss": stop_loss,  # Frontend expects camelCase
                    "tp1": tp1,
                    "tp2": tp2,
                    "rr": rr,
                    "reasons": reasons
                },
                "confluence": {
                    "price": price,
                    "rsi": rsi,
                    "macd": macd,
                    "macd_signal": macd_signal,
                    "ema": ema_data,
                    "fib50": fib50,
                    "fib618": fib618,
                    "long_score": long_score,
                    "short_score": short_score
                },
                "structure": {
                    "trend": structure_trend,
                    "swing_highs": swing_highs,
                    "swing_lows": swing_lows,
                    "bos_signals": bos_signals,
                    "choch_signals": choch_signals
                },
                "latest": analysis.get('latest', {}),
                "ohlc_data": ohlc_data,  # Full OHLC for charting
                "timestamp": pd.Timestamp.now().isoformat(),
                "timeframe": f"{days}d",
                
                # Legacy support for existing integrations
                "data": {symbol: analysis}
            }
            
            return result
            
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            print(f"Error in IvishX analysis for {symbol}: {str(e)}")
            print(f"Full traceback: {error_details}")
            
            return {
                "success": False, 
                "error": str(e),
                "error_details": error_details,
                "symbol": symbol,
                "signal": {
                    "type": "ERROR",
                    "confidence": 0,
                    "entry": 0,
                    "stop_loss": 0,
                    "stopLoss": 0,
                    "tp1": 0,
                    "tp2": 0,
                    "rr": 0,
                    "reasons": [f"Analysis failed: {str(e)}"]
                }
            }


class ZApiAnalysisArgs(BaseModel):
    token_symbol: str = Field(..., description="Token symbol like 'ETH', 'BTC', 'SOL'")
    timeframe: str = Field("7d", description="Timeframe like '1h', '4h', '1d', '7d', '30d'")
    query: str = Field(None, description="Optional specific query about the token")


class ZApiTechnicalAnalysis(BaseTool):
    name: str = "ZApiTechnicalAnalysis"
    description: str = "Get professional technical analysis from Z-API for any cryptocurrency"
    args_schema: Type[BaseModel] = ZApiAnalysisArgs

    def _run(self, token_symbol: str, timeframe: str = "7d", query: str = None) -> dict:
        try:
            z_api_url = os.getenv('Z_API_URL', 'https://z-api.vistara.dev')
            z_api_key = os.getenv('Z_API_KEY', '379a53d04647ce19.HNaeHcnLZ-D4Eeh5rCfX6jBuqBqjYl5HGMc99hxeQPE')
            
            if not z_api_key:
                return {
                    "success": False,
                    "error": "Z_API_KEY not configured",
                    "token_symbol": token_symbol
                }
            
            # Default query if none provided
            if not query:
                query = f"What's the technical analysis for {token_symbol} right now?"
            
            payload = {
                "token_symbol": token_symbol.upper(),
                "query": query,
                "timeframe": timeframe
            }
            
            response = requests.post(
                f"{z_api_url}/v1/analyze",
                headers={
                    "X-API-Key": z_api_key,
                    "Content-Type": "application/json"
                },
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                return {
                    "success": True,
                    "token_symbol": token_symbol,
                    "timeframe": timeframe,
                    "query": query,
                    "analysis": data,
                    "timestamp": pd.Timestamp.now().isoformat()
                }
            else:
                return {
                    "success": False,
                    "error": f"Z-API returned status {response.status_code}: {response.text}",
                    "token_symbol": token_symbol,
                    "status_code": response.status_code
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": f"Z-API call failed: {str(e)}",
                "token_symbol": token_symbol
            }


class CombinedAnalysisArgs(BaseModel):
    symbol: str = Field(..., description="Symbol like 'ethereum', 'bitcoin', 'solana'")
    days: int = Field(30, description="Number of days for IvishX analysis")
    timeframe: str = Field("7d", description="Timeframe for Z-API analysis")


class CombinedTechnicalAnalysis(BaseTool):
    name: str = "CombinedTechnicalAnalysis"
    description: str = "Get both IvishX confluence analysis and Z-API technical analysis in parallel"
    args_schema: Type[BaseModel] = CombinedAnalysisArgs

    def _run_ivishx(self, symbol: str, days: int) -> dict:
        """Run IvishX analysis"""
        ivishx_tool = IvishXAnalyzeTool()
        print(f"Running IvishX analysis for {symbol} with {days} days")
        return ivishx_tool._run(symbol, days)

    def _run_zapi(self, symbol: str, timeframe: str) -> dict:
        """Run Z-API analysis"""
        # Convert symbol to token format for Z-API
        symbol_map = {
            'ethereum': 'ETH',
            'bitcoin': 'BTC', 
            'solana': 'SOL',
            'binancecoin': 'BNB',
            'cardano': 'ADA',
            'ripple': 'XRP',
            'dogecoin': 'DOGE'
        }
        token_symbol = symbol_map.get(symbol.lower(), symbol.upper())
        
        zapi_tool = ZApiTechnicalAnalysis()
        return zapi_tool._run(token_symbol, timeframe)

    def _run(self, symbol: str, days: int = 30, timeframe: str = "7d") -> dict:
        """Run both analyses in parallel"""
        try:
            print(f"Running CombinedTechnicalAnalysis for {symbol} with {days} days and {timeframe} timeframe")
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                # Submit both tasks
                ivishx_future = executor.submit(self._run_ivishx, symbol, days)
                zapi_future = executor.submit(self._run_zapi, symbol, timeframe)
                
                # Get results (this will wait for both to complete)
                ivishx_result = ivishx_future.result(timeout=60)
                zapi_result = zapi_future.result(timeout=60)
                
                return {
                    "success": True,
                    "symbol": symbol,
                    "combined_analysis": {
                        "ivishx_confluence": ivishx_result,
                        "zapi_technical": zapi_result
                    },
                    "summary": {
                        "ivishx_signal": ivishx_result.get('signal', {}).get('type', 'UNKNOWN'),
                        "ivishx_confidence": ivishx_result.get('signal', {}).get('confidence', 0),
                        "zapi_success": zapi_result.get('success', False),
                        "both_successful": ivishx_result.get('success', False) and zapi_result.get('success', False)
                    },
                    "timestamp": pd.Timestamp.now().isoformat()
                }
                
        except concurrent.futures.TimeoutError:
            return {
                "success": False,
                "error": "Analysis timed out",
                "symbol": symbol
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Combined analysis failed: {str(e)}",
                "symbol": symbol
            }