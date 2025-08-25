import pandas as pd
from dataclasses import dataclass
from typing import Dict, Any, Optional, List
from .indicators import add_indicators, add_fib_levels
from .structure import find_swings, detect_bos_choch


@dataclass
class IvishXConfig:
    swing_lookback: int = 20
    near_pct_fib: float = 0.02
    near_pct_ema: float = 0.015
    min_confluence: int = 4
    mtf_confirm: bool = False
    mtf_bias_weight: int = 1


@dataclass
class IvishXSignal:
    type: str
    confidence: int
    entry: float
    stop_loss: float
    tp1: float
    tp2: float
    rr: float
    reasons: List[str]


class IvishXAnalyzer:
    def __init__(self, config: Optional[IvishXConfig] = None):
        self.cfg = config or IvishXConfig()

    def prepare(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df = add_indicators(df)
        df = add_fib_levels(df, swing_lookback=self.cfg.swing_lookback)
        return df

    def confluence(self, df: pd.DataFrame, structure: Dict[str, Any]) -> Dict[str, Any]:
        last = df.iloc[-1]
        price = float(last['close'])
        ema20, ema50, ema81, ema100, ema200 = map(float, (last['EMA_20'], last['EMA_50'], last['EMA_81'], last['EMA_100'], last['EMA_200']))
        rsi = float(last['RSI_14'])
        macd, sig = float(last['MACD']), float(last['MACD_Signal'])

        recent = df.tail(10)
        fib50 = float(recent['Fib_50'].dropna().iloc[-1]) if recent['Fib_50'].notna().any() else 0.0
        fib618 = float(recent['Fib_618'].dropna().iloc[-1]) if recent['Fib_618'].notna().any() else 0.0

        near_fib = (abs(price - fib50) / price < self.cfg.near_pct_fib) or (abs(price - fib618) / price < self.cfg.near_pct_fib) if (fib50 and fib618) else False
        near_ema = (abs(price - ema81) / price < self.cfg.near_pct_ema) or (abs(price - ema100) / price < self.cfg.near_pct_ema)

        long_score = 0
        long_reasons = []
        if price > ema200:
            long_score += 2; long_reasons.append("Price > EMA200")
        if ema20 > ema50 > ema81 > ema100 > ema200:
            long_score += 2; long_reasons.append("EMA 20>50>81>100>200")
        if any(s['type'] == 'BULLISH_CHOCH' for s in structure['choch_signals']):
            long_score += 1; long_reasons.append("Bullish CHoCH")
        if any(s['type'] == 'BULLISH_BOS' for s in structure['bos_signals']):
            long_score += 1; long_reasons.append("Bullish BOS")
        if near_fib and near_ema:
            long_score += 2; long_reasons.append("Fib(50/61.8) + EMA(81/100) confluence")
        if 50 < rsi < 70:
            long_score += 1; long_reasons.append(f"RSI {rsi:.1f} (bull zone)")
        if macd > sig and macd > 0:
            long_score += 1; long_reasons.append("MACD bullish crossover")
        if structure['structure_trend'] == 'BULLISH':
            long_score += 1; long_reasons.append("Clean bullish structure")

        short_score = 0
        short_reasons = []
        if price < ema200:
            short_score += 2; short_reasons.append("Price < EMA200")
        if ema200 > ema100 > ema81 > ema50 > ema20:
            short_score += 2; short_reasons.append("EMA 200>100>81>50>20")
        if any(s['type'] == 'BEARISH_CHOCH' for s in structure['choch_signals']):
            short_score += 1; short_reasons.append("Bearish CHoCH")
        if any(s['type'] == 'BEARISH_BOS' for s in structure['bos_signals']):
            short_score += 1; short_reasons.append("Bearish BOS")
        if near_fib and near_ema:
            short_score += 2; short_reasons.append("Fib(50/61.8) + EMA(81/100) confluence")
        if 30 < rsi < 50:
            short_score += 1; short_reasons.append(f"RSI {rsi:.1f} (bear zone)")
        if macd < sig and macd < 0:
            short_score += 1; short_reasons.append("MACD bearish crossover")
        if structure['structure_trend'] == 'BEARISH':
            short_score += 1; short_reasons.append("Clean bearish structure")

        return {
            'price': price,
            'ema': (ema20, ema50, ema81, ema100, ema200),
            'rsi': rsi,
            'macd': macd, 'macd_signal': sig,
            'fib50': fib50, 'fib618': fib618,
            'long': {'score': long_score, 'reasons': long_reasons},
            'short': {'score': short_score, 'reasons': short_reasons}
        }

    def build_signal(self, df: pd.DataFrame, conf: Dict[str, Any], structure: Dict[str, Any]) -> IvishXSignal:
        price = conf['price']
        ema20, ema50, ema81, ema100, ema200 = conf['ema']
        if conf['long']['score'] >= self.cfg.min_confluence and conf['long']['score'] >= conf['short']['score']:
            entry = price
            sl = min(ema81, ema100) * 0.99
            highs_above = [h for idx, h in structure['swing_highs'] if h > price]
            tp1 = (min(highs_above) * 0.99) if highs_above else price * 1.015
            tp2 = price * 1.03
            risk = max(entry - sl, 1e-9)
            rr = (tp1 - entry) / risk
            return IvishXSignal('LONG', conf['long']['score'], float(entry), float(sl), float(tp1), float(tp2), float(rr), conf['long']['reasons'])
        if conf['short']['score'] >= self.cfg.min_confluence and conf['short']['score'] > conf['long']['score']:
            entry = price
            sl = max(ema81, ema100) * 1.01
            lows_below = [l for idx, l in structure['swing_lows'] if l < price]
            tp1 = (max(lows_below) * 1.01) if lows_below else price * 0.985
            tp2 = price * 0.97
            risk = max(sl - entry, 1e-9)
            rr = (entry - tp1) / risk
            return IvishXSignal('SHORT', conf['short']['score'], float(entry), float(sl), float(tp1), float(tp2), float(rr), conf['short']['reasons'])
        return IvishXSignal('WAIT', max(conf['long']['score'], conf['short']['score']), float(price), 0.0, 0.0, 0.0, 0.0, ['Insufficient confluence'])

    def analyze(self, df: pd.DataFrame) -> Dict[str, Any]:
        dfp = self.prepare(df)
        swings_h, swings_l = find_swings(dfp, left=2, right=2)
        structure = detect_bos_choch(dfp, swings_h, swings_l)
        conf = self.confluence(dfp, structure)
        signal = self.build_signal(dfp, conf, structure)
        return {
            'latest': dfp.iloc[-1][['open', 'high', 'low', 'close', 'volume']].to_dict(),
            'structure': structure,
            'confluence': conf,
            'signal': signal.__dict__,
        }






