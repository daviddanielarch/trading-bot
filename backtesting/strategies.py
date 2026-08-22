"""Ten long-biased 1h strategies tuned for bullish BTC markets."""

from dataclasses import dataclass
from typing import Callable

import pandas as pd

from backtesting.indicators import (
    adx,
    bollinger_bands,
    ema,
    highest_high,
    macd,
    roc,
    rsi,
    sma,
    supertrend,
)


@dataclass(frozen=True)
class Strategy:
    name: str
    description: str
    generate_signals: Callable[[pd.DataFrame], pd.Series]


def _cross_above(a: pd.Series, b: pd.Series) -> pd.Series:
    return (a > b) & (a.shift(1) <= b.shift(1))


def _cross_below(a: pd.Series, b: pd.Series) -> pd.Series:
    return (a < b) & (a.shift(1) >= b.shift(1))


def ema_cross_12_26(df: pd.DataFrame) -> pd.Series:
    """Fast EMA crosses slow EMA — classic trend following."""
    close = df["Close"]
    fast = ema(close, 12)
    slow = ema(close, 26)
    entries = _cross_above(fast, slow)
    exits = _cross_below(fast, slow)
    return _hold_until_exit(entries, exits)


def ema_cross_21_55(df: pd.DataFrame) -> pd.Series:
    """Medium-term EMA crossover for sustained bull trends."""
    close = df["Close"]
    fast = ema(close, 21)
    slow = ema(close, 55)
    entries = _cross_above(fast, slow)
    exits = _cross_below(fast, slow)
    return _hold_until_exit(entries, exits)


def rsi_pullback_uptrend(df: pd.DataFrame) -> pd.Series:
    """Buy RSI recovery above 50 while price stays above 200 EMA."""
    close = df["Close"]
    trend = close > ema(close, 200)
    r = rsi(close, 14)
    entries = trend & _cross_above(r, pd.Series(50.0, index=close.index)) & (r.shift(1) < 45)
    exits = _cross_below(r, pd.Series(40.0, index=close.index))
    return _hold_until_exit(entries, exits)


def breakout_20_high(df: pd.DataFrame) -> pd.Series:
    """Breakout above 20-period high; exit below 10 EMA."""
    close = df["Close"]
    high = df["High"]
    prev_high = highest_high(high, 20).shift(1)
    entries = close > prev_high
    exit_ema = ema(close, 10)
    exits = _cross_below(close, exit_ema)
    return _hold_until_exit(entries, exits)


def macd_bull_cross(df: pd.DataFrame) -> pd.Series:
    """MACD line crosses above signal line."""
    close = df["Close"]
    line, sig = macd(close)
    entries = _cross_above(line, sig)
    exits = _cross_below(line, sig)
    return _hold_until_exit(entries, exits)


def bollinger_squeeze_breakout(df: pd.DataFrame) -> pd.Series:
    """Squeeze (narrow bands) then close above upper band."""
    close = df["Close"]
    upper, mid, _, width = bollinger_bands(close, 20, 2.0)
    squeeze = width < width.rolling(50).quantile(0.25)
    entries = squeeze.shift(1) & (close > upper)
    exits = close < mid
    return _hold_until_exit(entries, exits)


def adx_di_trend(df: pd.DataFrame) -> pd.Series:
    """Strong trend: ADX > 25 and +DI dominates -DI."""
    high, low, close = df["High"], df["Low"], df["Close"]
    adx_val, plus_di, minus_di = adx(high, low, close, 14)
    trend_on = (adx_val > 25) & (plus_di > minus_di)
    entries = trend_on & ~trend_on.shift(1).fillna(False)
    exits = (adx_val < 20) | (plus_di < minus_di)
    return _hold_until_exit(entries, exits)


def triple_ema_pullback(df: pd.DataFrame) -> pd.Series:
    """EMA stack (8>21>55) and bounce from EMA21."""
    close = df["Close"]
    e8 = ema(close, 8)
    e21 = ema(close, 21)
    e55 = ema(close, 55)
    stack = (e8 > e21) & (e21 > e55)
    touched = close <= e21 * 1.002
    entries = stack & touched & _cross_above(close, e21)
    exits = _cross_below(close, e55)
    return _hold_until_exit(entries, exits)


def momentum_roc(df: pd.DataFrame) -> pd.Series:
    """ROC momentum with price above SMA50."""
    close = df["Close"]
    r = roc(close, 10)
    above_sma = close > sma(close, 50)
    entries = above_sma & _cross_above(r, pd.Series(2.0, index=close.index))
    exits = _cross_below(r, pd.Series(0.0, index=close.index)) | _cross_below(close, sma(close, 50))
    return _hold_until_exit(entries, exits)


def supertrend_bull(df: pd.DataFrame) -> pd.Series:
    """Long when Supertrend flips bullish."""
    high, low, close = df["High"], df["Low"], df["Close"]
    _, bullish = supertrend(high, low, close, 10, 3.0)
    entries = bullish & ~bullish.shift(1).fillna(False)
    exits = ~bullish & bullish.shift(1).fillna(True)
    return _hold_until_exit(entries, exits)


def golden_cross_50_200(df: pd.DataFrame) -> pd.Series:
    """Golden cross on 1h: EMA50 crosses above EMA200."""
    close = df["Close"]
    fast = ema(close, 50)
    slow = ema(close, 200)
    entries = _cross_above(fast, slow)
    exits = _cross_below(fast, slow)
    return _hold_until_exit(entries, exits)


def _hold_until_exit(entries: pd.Series, exits: pd.Series) -> pd.Series:
    """Convert entry/exit events into a position series (1 = long, 0 = flat)."""
    position = pd.Series(0, index=entries.index, dtype=int)
    in_pos = False
    for i in range(len(position)):
        if not in_pos and entries.iloc[i]:
            in_pos = True
        elif in_pos and exits.iloc[i]:
            in_pos = False
        position.iloc[i] = 1 if in_pos else 0
    return position


ALL_STRATEGIES: list[Strategy] = [
    Strategy(
        "1_EMA_Cross_12_26",
        "Cruce EMA 12/26 — seguimiento de tendencia rápido",
        ema_cross_12_26,
    ),
    Strategy(
        "2_EMA_Cross_21_55",
        "Cruce EMA 21/55 — tendencia media en bull market",
        ema_cross_21_55,
    ),
    Strategy(
        "3_RSI_Pullback",
        "Pullback RSI en uptrend (precio > EMA200)",
        rsi_pullback_uptrend,
    ),
    Strategy(
        "4_Breakout_20H",
        "Ruptura de máximo 20h con salida en EMA10",
        breakout_20_high,
    ),
    Strategy(
        "5_MACD_Cross",
        "Cruce MACD alcista",
        macd_bull_cross,
    ),
    Strategy(
        "6_BB_Squeeze_Break",
        "Squeeze Bollinger + ruptura banda superior",
        bollinger_squeeze_breakout,
    ),
    Strategy(
        "7_ADX_DI_Trend",
        "ADX > 25 con +DI > -DI",
        adx_di_trend,
    ),
    Strategy(
        "8_Triple_EMA_Pullback",
        "Stack EMA 8/21/55 + rebote en EMA21",
        triple_ema_pullback,
    ),
    Strategy(
        "9_Momentum_ROC",
        "ROC > 2% con precio sobre SMA50",
        momentum_roc,
    ),
    Strategy(
        "10_Supertrend_Bull",
        "Entrada en flip alcista Supertrend (10,3)",
        supertrend_bull,
    ),
]
