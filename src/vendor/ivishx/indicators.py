import pandas as pd
import numpy as np


def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = (delta.where(delta > 0, 0.0)).ewm(alpha=1 / period, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0.0)).ewm(alpha=1 / period, adjust=False).mean()
    rs = gain / (loss.replace(0, np.nan))
    rsi_val = 100 - (100 / (1 + rs))
    return rsi_val.fillna(50)


def macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    ema_fast = ema(series, fast)
    ema_slow = ema(series, slow)
    macd_line = ema_fast - ema_slow
    signal_line = ema(macd_line, signal)
    hist = macd_line - signal_line
    return macd_line, signal_line, hist


def candle_patterns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df['bullish_engulfing'] = (
        (df['close'] > df['open']) & (df['open'].shift(1) > df['close'].shift(1)) &
        (df['close'] >= df['open'].shift(1)) & (df['open'] <= df['close'].shift(1))
    )
    df['bearish_engulfing'] = (
        (df['close'] < df['open']) & (df['open'].shift(1) < df['close'].shift(1)) &
        (df['close'] <= df['open'].shift(1)) & (df['open'] >= df['close'].shift(1))
    )
    return df


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df['EMA_20'] = ema(df['close'], 20)
    df['EMA_50'] = ema(df['close'], 50)
    df['EMA_81'] = ema(df['close'], 81)
    df['EMA_100'] = ema(df['close'], 100)
    df['EMA_200'] = ema(df['close'], 200)
    df['RSI_14'] = rsi(df['close'], 14)
    df['MACD'], df['MACD_Signal'], df['MACD_Hist'] = macd(df['close'], 12, 26, 9)
    df = candle_patterns(df)
    return df


def add_fib_levels(df: pd.DataFrame, swing_lookback: int = 20) -> pd.DataFrame:
    df = df.copy()
    df['Swing_High'] = df['high'].rolling(window=swing_lookback).max()
    df['Swing_Low'] = df['low'].rolling(window=swing_lookback).min()
    rng = (df['Swing_High'] - df['Swing_Low']).replace(0, np.nan)
    df['Fib_50'] = df['Swing_High'] - rng * 0.5
    df['Fib_618'] = df['Swing_High'] - rng * 0.618
    return df






