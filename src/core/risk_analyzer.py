"""
Risk Analysis Service for DeFi Operations
Implements comprehensive risk assessment for DeFi trades and operations
"""

from typing import Dict, Any, List, Optional
from pydantic import BaseModel
from enum import Enum
import numpy as np
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    EXTREME = "extreme"

class RiskFactor(BaseModel):
    name: str
    score: float
    weight: float
    description: str
    recommendations: List[str]

class RiskAssessment(BaseModel):
    overall_risk: RiskLevel
    risk_score: float
    factors: List[RiskFactor]
    timestamp: datetime
    recommendations: List[str]
    warning_flags: List[str]

class RiskAnalyzer:
    def __init__(self):
        self.volatility_cache = {}
        self.liquidity_thresholds = {
            "SOL": 1000000,  # $1M liquidity threshold
            "USDC": 5000000,
            "default": 100000
        }
        self.price_impact_thresholds = {
            "low": 0.001,    # 0.1%
            "medium": 0.005, # 0.5%
            "high": 0.01     # 1%
        }
        
    async def analyze_trade_risk(
        self,
        token: str,
        amount: float,
        price: float,
        market_data: Dict[str, Any]
    ) -> RiskAssessment:
        """Comprehensive trade risk analysis"""
        try:
            # Calculate individual risk factors
            volatility_risk = await self._analyze_volatility(token, market_data)
            liquidity_risk = await self._analyze_liquidity(token, amount, market_data)
            timing_risk = await self._analyze_timing(token, price, market_data)
            market_risk = await self._analyze_market_conditions(token, market_data)
            
            # Combine risk factors
            risk_factors = [
                volatility_risk,
                liquidity_risk,
                timing_risk,
                market_risk
            ]
            
            # Calculate overall risk score (weighted average)
            overall_score = sum(rf.score * rf.weight for rf in risk_factors)
            
            # Determine risk level
            risk_level = self._determine_risk_level(overall_score)
            
            # Generate recommendations
            recommendations = self._generate_recommendations(
                risk_factors,
                risk_level,
                amount
            )
            
            # Generate warning flags
            warning_flags = self._generate_warning_flags(
                risk_factors,
                amount,
                market_data
            )
            
            return RiskAssessment(
                overall_risk=risk_level,
                risk_score=overall_score,
                factors=risk_factors,
                timestamp=datetime.now(),
                recommendations=recommendations,
                warning_flags=warning_flags
            )
            
        except Exception as e:
            logger.error(f"Error in risk analysis: {str(e)}", exc_info=True)
            raise
            
    async def _analyze_volatility(
        self,
        token: str,
        market_data: Dict[str, Any]
    ) -> RiskFactor:
        """Analyze price volatility risk"""
        # Calculate historical volatility
        prices = market_data.get("price_history", [])
        if len(prices) > 1:
            returns = np.diff(np.log(prices))
            volatility = np.std(returns) * np.sqrt(365)
            
            score = min(volatility / 2, 1.0)  # Normalize to 0-1
            recommendations = []
            
            if volatility > 0.8:
                recommendations.append("Consider using a lower position size due to high volatility")
            if volatility > 0.5:
                recommendations.append("Use tight stop losses")
            
            return RiskFactor(
                name="Volatility Risk",
                score=score,
                weight=0.3,
                description=f"Historical volatility: {volatility:.2%}",
                recommendations=recommendations
            )
        
        return RiskFactor(
            name="Volatility Risk",
            score=0.5,  # Default medium risk when no data
            weight=0.3,
            description="Insufficient price history for volatility calculation",
            recommendations=["Monitor price action closely due to limited historical data"]
        )
            
    async def _analyze_liquidity(
        self,
        token: str,
        amount: float,
        market_data: Dict[str, Any]
    ) -> RiskFactor:
        """Analyze liquidity risk"""
        liquidity = market_data.get("liquidity", 0)
        threshold = self.liquidity_thresholds.get(token, self.liquidity_thresholds["default"])
        
        # Calculate what percentage of liquidity we're using
        liquidity_usage = amount / liquidity if liquidity > 0 else 1
        
        score = min(liquidity_usage * 5, 1.0)  # Normalize to 0-1
        recommendations = []
        
        if liquidity_usage > 0.1:
            recommendations.append("Consider splitting the trade into smaller parts")
        if liquidity_usage > 0.05:
            recommendations.append("Use a longer execution timeframe")
        
        return RiskFactor(
            name="Liquidity Risk",
            score=score,
            weight=0.25,
            description=f"Using {liquidity_usage:.2%} of available liquidity",
            recommendations=recommendations
        )
            
    async def _analyze_timing(
        self,
        token: str,
        price: float,
        market_data: Dict[str, Any]
    ) -> RiskFactor:
        """Analyze market timing risk"""
        recent_high = market_data.get("recent_high", price)
        recent_low = market_data.get("recent_low", price)
        
        if recent_high == recent_low:
            return RiskFactor(
                name="Timing Risk",
                score=0.5,
                weight=0.2,
                description="Insufficient price range data",
                recommendations=["Monitor price action before executing"]
            )
            
        # Calculate where current price is in the range
        price_position = (price - recent_low) / (recent_high - recent_low)
        
        # Higher risk if price is at extremes
        score = abs(price_position - 0.5) * 2
        recommendations = []
        
        if price_position > 0.8:
            recommendations.append("Price near recent highs - consider waiting for pullback")
        elif price_position < 0.2:
            recommendations.append("Price near recent lows - watch for reversal confirmation")
        
        return RiskFactor(
            name="Timing Risk",
            score=score,
            weight=0.2,
            description=f"Price position in range: {price_position:.2%}",
            recommendations=recommendations
        )
            
    async def _analyze_market_conditions(
        self,
        token: str,
        market_data: Dict[str, Any]
    ) -> RiskFactor:
        """Analyze general market conditions"""
        market_score = 0.5  # Default medium risk
        recommendations = []
        
        # Analyze trend
        trend = market_data.get("trend", "neutral")
        if trend == "strong_uptrend":
            market_score -= 0.2
        elif trend == "strong_downtrend":
            market_score += 0.2
            
        # Analyze correlation with market
        correlation = market_data.get("market_correlation", 0)
        if abs(correlation) > 0.8:
            recommendations.append("High market correlation - consider overall market conditions")
            
        # Analyze volume
        volume_ratio = market_data.get("volume_ratio", 1)
        if volume_ratio > 2:
            recommendations.append("Unusual high volume - watch for potential price moves")
            market_score += 0.1
            
        return RiskFactor(
            name="Market Conditions",
            score=min(max(market_score, 0), 1),
            weight=0.25,
            description=f"Market trend: {trend}, Correlation: {correlation:.2f}",
            recommendations=recommendations
        )
            
    def _determine_risk_level(self, score: float) -> RiskLevel:
        """Convert numerical score to risk level"""
        if score < 0.3:
            return RiskLevel.LOW
        elif score < 0.6:
            return RiskLevel.MEDIUM
        elif score < 0.8:
            return RiskLevel.HIGH
        else:
            return RiskLevel.EXTREME
            
    def _generate_recommendations(
        self,
        risk_factors: List[RiskFactor],
        risk_level: RiskLevel,
        amount: float
    ) -> List[str]:
        """Generate overall recommendations based on risk assessment"""
        recommendations = []
        
        # Collect all factor-specific recommendations
        for factor in risk_factors:
            recommendations.extend(factor.recommendations)
            
        # Add general recommendations based on risk level
        if risk_level == RiskLevel.HIGH:
            recommendations.append("Consider reducing position size")
            recommendations.append("Use strict stop losses")
        elif risk_level == RiskLevel.EXTREME:
            recommendations.append("Strongly consider postponing trade")
            recommendations.append("If proceeding, use minimum position size")
            
        # Add size-based recommendations
        if amount > 10000:
            recommendations.append("Large trade size - consider using DCA strategy")
            
        return list(set(recommendations))  # Remove duplicates
            
    def _generate_warning_flags(
        self,
        risk_factors: List[RiskFactor],
        amount: float,
        market_data: Dict[str, Any]
    ) -> List[str]:
        """Generate warning flags for high-risk situations"""
        warnings = []
        
        # Check for high-risk factors
        for factor in risk_factors:
            if factor.score > 0.8:
                warnings.append(f"High {factor.name.lower()}")
                
        # Check for unusual market conditions
        if market_data.get("volume_ratio", 1) > 3:
            warnings.append("Unusual market volume")
        if market_data.get("price_change_24h", 0) > 0.2:
            warnings.append("Large 24h price movement")
            
        # Check for size-related risks
        liquidity = market_data.get("liquidity", 0)
        if liquidity > 0 and amount / liquidity > 0.1:
            warnings.append("Trade size > 10% of liquidity")
            
        return warnings 