import yfinance as yf
import pandas as pd
from crewai import Agent, Crew, Task, Process
from crewai.tools import BaseTool
import numpy as np
from pydantic import BaseModel, Field
from typing import Type


class AnalysisSchema(BaseModel):
    ticker: str = Field(..., description="Stock ticker")


class FundamentalAnalysis(BaseTool):
    name: str = "Analyze a stock's fundamentals"
    description: str = "A tool to analyze stock fundamentals"
    args_schema: Type[BaseModel] = AnalysisSchema

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def _run(self, **kwargs):
        ticker = kwargs["ticker"]
        period = "1y"
        stock = yf.Ticker(ticker)

        history = stock.history(period=period)

        # Fetch latest available financial info
        info = stock.info

        fundamental_analysis = pd.DataFrame(
            {
                "Name": [info.get("longName", "N/A")],
                "Sector": [info.get("sector", "N/A")],
                "Industry": [info.get("industry", "N/A")],
                "Market Cap": [info.get("marketCap", "N/A")],
                "Current Price": [info.get("currentPrice", "N/A")],
                "52 Week High": [info.get("fiftyTwoWeekHigh", "N/A")],
                "52 Week Low": [info.get("fiftyTwoWeekLow", "N/A")],
                "PE Ratio": [info.get("trailingPE", "N/A")],
                "Forward PE": [info.get("forwardPE", "N/A")],
                "PEG Ratio": [info.get("pegRatio", "N/A")],
                "Price to Book": [info.get("priceToBook", "N/A")],
                "Dividend Yield": [info.get("dividendYield", "N/A")],
                "EPS (TTM)": [info.get("trailingEps", "N/A")],
                "Revenue Growth": [info.get("revenueGrowth", "N/A")],
                "Profit Margin": [info.get("profitMargins", "N/A")],
                "Free Cash Flow": [info.get("freeCashflow", "N/A")],
                "Debt to Equity": [info.get("debtToEquity", "N/A")],
                "Return on Equity": [info.get("returnOnEquity", "N/A")],
                "Operating Margin": [info.get("operatingMargins", "N/A")],
                "Quick Ratio": [info.get("quickRatio", "N/A")],
                "Current Ratio": [info.get("currentRatio", "N/A")],
                "Earnings Growth": [info.get("earningsGrowth", "N/A")],
                "Stock Price Avg (Period)": [history["Close"].mean()],
                "Stock Price Max (Period)": [history["Close"].max()],
                "Stock Price Min (Period)": [history["Close"].min()],
            }
        )

        return fundamental_analysis


class RiskAssessment(BaseTool):
    name: str = "Analyze a stock's risk"
    description: str = "A tool for risk assessment"
    args_schema: Type[BaseModel] = AnalysisSchema

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def _run(self, **kwargs):
        ticker = kwargs["ticker"]
        period = "1y"
        stock = yf.Ticker(ticker)
        history = stock.history(period=period)

        # Calculate daily returns
        returns = history["Close"].pct_change().dropna()

        # Calculate risk metrics
        volatility = returns.std() * np.sqrt(252)  # Annualized volatility
        beta = calculate_beta(
            returns, "^GSPC", period
        )  # Beta relative to S&P 500
        var_95 = np.percentile(returns, 5)  # 95% Value at Risk
        max_drawdown = calculate_max_drawdown(history["Close"])

        risk_assessment = pd.DataFrame(
            {
                "Annualized Volatility": [volatility],
                "Beta": [beta],
                "Value at Risk (95%)": [var_95],
                "Maximum Drawdown": [max_drawdown],
                "Sharpe Ratio": [calculate_sharpe_ratio(returns)],
                "Sortino Ratio": [calculate_sortino_ratio(returns)],
            }
        )

        return risk_assessment


def calculate_beta(stock_returns, market_ticker, period):
    market = yf.Ticker(market_ticker)
    market_history = market.history(period=period)
    market_returns = market_history["Close"].pct_change().dropna()

    # Align the dates of stock and market returns
    aligned_returns = pd.concat(
        [stock_returns, market_returns], axis=1
    ).dropna()

    covariance = aligned_returns.cov().iloc[0, 1]
    market_variance = market_returns.var()

    return covariance / market_variance


def calculate_max_drawdown(prices):
    peak = prices.cummax()
    drawdown = (prices - peak) / peak
    return drawdown.min()


def calculate_sharpe_ratio(returns, risk_free_rate=0.02):
    excess_returns = returns - risk_free_rate / 252
    return np.sqrt(252) * excess_returns.mean() / excess_returns.std()


def calculate_sortino_ratio(returns, risk_free_rate=0.02, target_return=0):
    excess_returns = returns - risk_free_rate / 252
    downside_returns = excess_returns[excess_returns < target_return]
    downside_deviation = np.sqrt(np.mean(downside_returns**2))
    return np.sqrt(252) * excess_returns.mean() / downside_deviation


class TechnicalAnalysis(BaseTool):
    name: str = "Analyze a stock's technicals"
    description: str = "A tool for technical analysis"
    args_schema: Type[BaseModel] = AnalysisSchema

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def _run(self, **kwargs):
        ticker = kwargs["ticker"]
        period = "1mo"
        stock = yf.Ticker(ticker)
        history = stock.history(period=period)

        # Calculate indicators
        history["SMA_50"] = history["Close"].rolling(window=50).mean()
        history["SMA_200"] = history["Close"].rolling(window=200).mean()
        history["RSI"] = calculate_rsi(history["Close"])
        history["MACD"], history["Signal"] = calculate_macd(history["Close"])

        latest = history.iloc[-1]

        analysis = pd.DataFrame(
            {
                "Indicator": [
                    "Current Price",
                    "50-day SMA",
                    "200-day SMA",
                    "RSI (14-day)",
                    "MACD",
                    "MACD Signal",
                    "Trend",
                    "MACD Signal",
                    "RSI Signal",
                ],
                "Value": [
                    f'${latest["Close"]:.2f}',
                    f'${latest["SMA_50"]:.2f}',
                    f'${latest["SMA_200"]:.2f}',
                    f'{latest["RSI"]:.2f}',
                    f'{latest["MACD"]:.2f}',
                    f'{latest["Signal"]:.2f}',
                    analyze_trend(latest),
                    analyze_macd(latest),
                    analyze_rsi(latest),
                ],
            }
        )

        return analysis


def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def calculate_macd(series, short_window=12, long_window=26, signal_window=9):
    short_ema = series.ewm(span=short_window, adjust=False).mean()
    long_ema = series.ewm(span=long_window, adjust=False).mean()
    macd = short_ema - long_ema
    signal = macd.ewm(span=signal_window, adjust=False).mean()
    return macd, signal


def analyze_trend(latest):
    if latest["Close"] > latest["SMA_50"] > latest["SMA_200"]:
        return "Bullish"
    elif latest["Close"] < latest["SMA_50"] < latest["SMA_200"]:
        return "Bearish"
    else:
        return "Neutral"


def analyze_macd(latest):
    if latest["MACD"] > latest["Signal"]:
        return "Bullish"
    else:
        return "Bearish"


def analyze_rsi(latest):
    if latest["RSI"] > 70:
        return "Overbought"
    elif latest["RSI"] < 30:
        return "Oversold"
    else:
        return "Neutral"


def analyze_bollinger_bands(latest):
    if latest["Close"] > latest["BB_Upper"]:
        return "Price above upper band (potential overbought)"
    elif latest["Close"] < latest["BB_Lower"]:
        return "Price below lower band (potential oversold)"
    else:
        return "Price within bands"


def format_number(self, value):
    if value != "N/A":
        return f"${value:,.2f}"
    else:
        return "N/A"


def interpret_pe_ratio(self, trailing_pe):
    if trailing_pe < 15:
        return "Undervalued"
    elif trailing_pe > 30:
        return "Overvalued"
    else:
        return "Neutral"


def interpret_price_to_book(self, price_to_book):
    if price_to_book < 1:
        return "Undervalued"
    elif price_to_book > 3:
        return "Overvalued"
    else:
        return "Neutral"


fundamental_agent = Agent(
    role="Fundamental Stock Analyst",
    goal="Analyze a given stock ticker based on various metrics",
    backstory="A stock researcher experienced in analyzing information about stocks, their relevant peer companies, the industry, and their various fundamental ratios",
    tools=[FundamentalAnalysis()],
    verbose=True,
    allow_delegation=False,
)

technical_agent = Agent(
    role="Technical Stock Analyst",
    goal="Analyze a given stock ticker based on in-depth technical analysis",
    backstory="A seasoned technical analyst with expertise in interpreting various technical indicators and trading stocks",
    tools=[TechnicalAnalysis(), RiskAssessment()],
    verbose=True,
    allow_delegation=False,
)

recommendation_agent = Agent(
    role="Stock Recommendation Agent",
    goal="Suggest whether a stock should be bought/sold based on the signals generated by fundamental and technical analysis, explaining the rationale",
    backstory="Experienced stock analyst capable of analyzing fundamental and technical reports",
    tools=[],
    verbose=True,
    allow_delegation=False,
)

fundamental_task = Task(
    description="Conduct a thorough analysis of a stock using the provided tool. Analyse fundamentals based on the company, sector, peers, and financial ratios like PE ratio",
    expected_output="Summary of stock's key financial metrics, financials, and a bullish/bearish signal based on the information provided",
    agent=fundamental_agent,
)

technical_task = Task(
    description="Conduct a thorough analysis of a stuck using the provided tool. Analyze various technical signals like MACD, RSI, etc.",
    expected_output="Summary of the stock's recent and projected future performance, and a bullish/bearish signal based on the technical analysis of various signals",
    agent=technical_agent,
)

recommendation_task = Task(
    description="",
    expected_output="Summary of the analysis of technical & fundamental agents, suggesting whether to buy or sell a stock",
    context=[fundamental_task, technical_task],
    agent=recommendation_agent,
)

crew = Crew(
    agents=[fundamental_agent, technical_agent, recommendation_agent],
    tasks=[fundamental_task, technical_task, recommendation_task],
    process=Process.sequential,
)

crew.kickoff(inputs={"query": "Analyze the AMZN ticker"})
