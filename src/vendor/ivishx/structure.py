import pandas as pd
from typing import List, Dict, Tuple


def find_swings(df: pd.DataFrame, left: int = 2, right: int = 2) -> Tuple[list, list]:
    highs = df['high'].values
    lows = df['low'].values
    swing_highs = []
    swing_lows = []
    for i in range(left, len(df) - right):
        is_high = all(highs[i] > highs[i - k - 1] for k in range(left)) and all(highs[i] > highs[i + k + 1] for k in range(right))
        is_low = all(lows[i] < lows[i - k - 1] for k in range(left)) and all(lows[i] < lows[i + k + 1] for k in range(right))
        if is_high:
            swing_highs.append((i, highs[i]))
        if is_low:
            swing_lows.append((i, lows[i]))
    return swing_highs, swing_lows


def detect_bos_choch(df: pd.DataFrame, swing_highs: list, swing_lows: list) -> Dict:
    closes = df['close'].values
    current = closes[-1]
    bos = []
    choch = []

    last_high = max(swing_highs[-3:], key=lambda x: x[1])[1] if swing_highs else None
    last_low = min(swing_lows[-3:], key=lambda x: x[1])[1] if swing_lows else None

    if last_high is not None and current > last_high * 1.001:
        bos.append({'type': 'BULLISH_BOS', 'level': float(last_high), 'confidence': 80})
    if last_low is not None and current < last_low * 0.999:
        bos.append({'type': 'BEARISH_BOS', 'level': float(last_low), 'confidence': 80})

    if len(swing_lows) >= 2 and len(swing_highs) >= 1:
        if swing_lows[-1][1] < swing_lows[-2][1] and current > max(h[1] for h in swing_highs[-2:]):
            choch.append({'type': 'BULLISH_CHOCH', 'level': float(swing_lows[-2][1]), 'confidence': 70})
    if len(swing_highs) >= 2 and len(swing_lows) >= 1:
        if swing_highs[-1][1] > swing_highs[-2][1] and current < min(l[1] for l in swing_lows[-2:]):
            choch.append({'type': 'BEARISH_CHOCH', 'level': float(swing_highs[-2][1]), 'confidence': 70})

    if bos:
        structure_trend = 'BULLISH' if bos[-1]['type'] == 'BULLISH_BOS' else 'BEARISH' if bos[-1]['type'] == 'BEARISH_BOS' else 'NEUTRAL'
    else:
        structure_trend = 'NEUTRAL'

    return {
        'swing_highs': swing_highs,
        'swing_lows': swing_lows,
        'bos_signals': bos,
        'choch_signals': choch,
        'structure_trend': structure_trend
    }






