#!/usr/bin/env python3
"""
Vistara API Integration for Advanced Technical Analysis
Professional chart analysis with z-api.vistara.dev
"""

import os
import json
import aiohttp
import asyncio
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)

@dataclass
class VistaraAnalysis:
    """Vistara analysis result"""
    symbol: str
    price: float
    price_change_24h: float
    rsi: float
    macd_signal: str
    volume: float
    price_trend: str
    analysis_text: str
    chart_url: str
    full_charts: list
    confidence_score: float
    request_id: str

class VistaraAnalyzer:
    """Professional crypto analysis using Vistara API"""
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv('VISTARA_API_KEY', '379a53d04647ce19.HNaeHcnLZ-D4Eeh5rCfX6jBuqBqjYl5HGMc99hxeQPE')
        self.base_url = "https://z-api.vistara.dev"
        
    async def analyze(self, symbol: str, query: str = None, timeframe: str = "7d") -> Optional[VistaraAnalysis]:
        """Get comprehensive analysis from Vistara API with retry logic"""
        return await self.analyze_with_retry(symbol, query, timeframe, max_retries=3)
    
    async def analyze_with_retry(self, symbol: str, query: str = None, timeframe: str = "7d", max_retries: int = 3) -> Optional[VistaraAnalysis]:
        """Get analysis with exponential backoff retry logic"""
        if not query:
            query = f"What's the technical analysis for {symbol} right now?"
        
        for attempt in range(max_retries):
            try:
                logger.info(f"Vistara analysis attempt {attempt + 1}/{max_retries} for {symbol}")
                
                # Prepare request
                headers = {
                    'X-API-Key': self.api_key,
                    'Content-Type': 'application/json'
                }
                
                data = {
                    "token_symbol": symbol.upper(),
                    "query": query,
                    "timeframe": timeframe
                }
                
                # Use shorter timeout for faster retries
                timeout = aiohttp.ClientTimeout(total=15, connect=5)
                
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.post(
                        f"{self.base_url}/v1/analyze",
                        headers=headers,
                        json=data
                    ) as response:
                        if response.status == 200:
                            result = await response.json()
                            logger.info(f"✅ Vistara analysis successful for {symbol}")
                            return self._parse_analysis(result)
                        else:
                            error_text = await response.text()
                            logger.warning(f"Vistara API error {response.status}: {error_text}")
                            if attempt == max_retries - 1:
                                return self._create_fallback_analysis(symbol)
                            
            except (TimeoutError, asyncio.TimeoutError, aiohttp.ClientError) as e:
                logger.warning(f"Vistara attempt {attempt + 1} failed: {e}")
                if attempt == max_retries - 1:
                    logger.error(f"Vistara analysis failed after {max_retries} attempts for {symbol}")
                    return self._create_fallback_analysis(symbol)
                
                # Exponential backoff: 2, 4, 8 seconds
                wait_time = 2 ** attempt
                logger.info(f"Retrying in {wait_time} seconds...")
                await asyncio.sleep(wait_time)
                
            except Exception as e:
                logger.error(f"Unexpected error in Vistara analysis: {e}")
                if attempt == max_retries - 1:
                    return self._create_fallback_analysis(symbol)
                await asyncio.sleep(2 ** attempt)
        
        return self._create_fallback_analysis(symbol)
    
    def _create_fallback_analysis(self, symbol: str) -> VistaraAnalysis:
        """Create fallback analysis when Vistara API fails"""
        logger.info(f"Creating fallback analysis for {symbol}")
        return VistaraAnalysis(
            symbol=symbol.upper(),
            price=0.0,
            price_change_24h=0.0,
            rsi=50.0,
            macd_signal="NEUTRAL",
            volume=0.0,
            price_trend="neutral",
            analysis_text=f"⚠️ Vistara API temporarily unavailable. Manual analysis recommended for {symbol}.",
            chart_url="",
            full_charts=[],
            confidence_score=0.3,
            request_id=f"fallback_{symbol}_{int(datetime.now().timestamp())}"
        )
    
    def _parse_analysis(self, result: Dict[str, Any]) -> VistaraAnalysis:
        """Parse Vistara API response"""
        token_data = result.get('token_data', {})
        technical_data = result.get('technical_data', {})
        macd_data = technical_data.get('macd', {})
        
        return VistaraAnalysis(
            symbol=token_data.get('symbol', '').upper(),
            price=float(token_data.get('price', 0)),
            price_change_24h=float(token_data.get('price_change_24h', 0)),
            rsi=float(technical_data.get('rsi', 50)),
            macd_signal=self._get_macd_signal(macd_data),
            volume=float(technical_data.get('volume', 0)),
            price_trend=technical_data.get('price_trend', 'neutral'),
            analysis_text=result.get('analysis', ''),
            chart_url=result.get('chart_url', ''),
            full_charts=result.get('full_charts', []),
            confidence_score=float(result.get('confidence_score', 0.5)),
            request_id=result.get('request_id', '')
        )
    
    def _get_macd_signal(self, macd_data: Dict[str, Any]) -> str:
        """Interpret MACD signal"""
        macd = macd_data.get('macd', 0)
        signal = macd_data.get('signal', 0)
        histogram = macd_data.get('histogram', 0)
        
        if histogram > 0 and macd > signal:
            return "BULLISH"
        elif histogram < 0 and macd < signal:
            return "BEARISH"
        else:
            return "NEUTRAL"
    
    def format_analysis_for_telegram(self, analysis: VistaraAnalysis) -> tuple[str, str]:
        """Format analysis for beautiful Telegram display"""
        
        # Price change formatting
        price_emoji = "🟢" if analysis.price_change_24h >= 0 else "🔴"
        price_sign = "+" if analysis.price_change_24h >= 0 else ""
        
        # RSI interpretation
        if analysis.rsi < 30:
            rsi_status = "🟢 OVERSOLD"
        elif analysis.rsi > 70:
            rsi_status = "🔴 OVERBOUGHT"
        else:
            rsi_status = "⚪ NEUTRAL"
        
        # MACD emoji
        macd_emoji = "🟢" if analysis.macd_signal == "BULLISH" else "🔴" if analysis.macd_signal == "BEARISH" else "⚪"
        
        # Trend emoji
        trend_emoji = "📈" if analysis.price_trend == "bullish" else "📉" if analysis.price_trend == "bearish" else "➡️"
        
        # Confidence bar
        confidence_percentage = int(analysis.confidence_score * 100)
        confidence_bar = "█" * int(confidence_percentage / 10) + "░" * (10 - int(confidence_percentage / 10))
        
        analysis_text = f"""
┌──────── 📊 **{analysis.symbol} ANALYSIS** ────────┐
│                                                         │
│  💰 **Price**: ${analysis.price:,.2f} ({price_sign}{analysis.price_change_24h:.2f}%) {price_emoji}  │
│  📊 **Volume**: ${analysis.volume/1e9:.2f}B                        │
│                                                         │
└─────────────────────────────────────┘

📈 **TECHNICAL INDICATORS**
┌─────────────────────────────────────┐
│ 🎯 **RSI**: {analysis.rsi:.1f} - {rsi_status}              │
│ {macd_emoji} **MACD**: {analysis.macd_signal}                        │
│ {trend_emoji} **Trend**: {analysis.price_trend.upper()}                      │
│                                                         │
│ 🔮 **AI Confidence**: {confidence_percentage}%                     │
│ {confidence_bar}                      │
└─────────────────────────────────────┘

🧠 **PROFESSIONAL ANALYSIS**
{analysis.analysis_text}

📊 **CHARTS AVAILABLE**
• Main Chart: [View Analysis Chart]({analysis.chart_url})
"""
        
        return analysis_text, analysis.chart_url

# Global analyzer instance
_vistara_analyzer = None

def get_vistara_analyzer() -> VistaraAnalyzer:
    """Get global Vistara analyzer instance"""
    global _vistara_analyzer
    if _vistara_analyzer is None:
        _vistara_analyzer = VistaraAnalyzer()
    return _vistara_analyzer