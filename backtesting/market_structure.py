"""Market structure levels for structural stop-loss placement."""

import numpy as np
import pandas as pd


def rolling_swing_low(low: pd.Series, period: int) -> pd.Series:
    """Minimum low over the last `period` bars (includes current bar)."""
    return low.rolling(period, min_periods=period).min()


def pre_entry_swing_low(low: pd.Series, period: int) -> pd.Series:
    """Swing low using only completed bars before the current bar."""
    return low.rolling(period, min_periods=period).min().shift(1)


def swing_low_with_buffer(level: pd.Series, buffer_pct: float) -> pd.Series:
    return level * (1 - buffer_pct / 100.0)


def last_pivot_low(low: pd.Series, left: int = 2, right: int = 2) -> pd.Series:
    """
    Forward-filled level of the most recent pivot low.
    Pivot at i when low[i] is the minimum in [i-left, i+right].
    """
    n = len(low)
    pivot_level = pd.Series(np.nan, index=low.index, dtype=float)
    values = low.values

    for i in range(left, n - right):
        window = values[i - left : i + right + 1]
        if values[i] == window.min():
            pivot_level.iloc[i] = values[i]

    return pivot_level.ffill()


def structural_stop_level(
    low: pd.Series,
    kind: str,
    period: int,
    buffer_pct: float,
    pivot_left: int = 2,
    pivot_right: int = 2,
) -> pd.Series:
    """Per-bar reference support level (before buffer)."""
    if kind == "fixed_swing":
        return pre_entry_swing_low(low, period)
    if kind == "trail_swing":
        return rolling_swing_low(low, period)
    if kind == "entry_low":
        return low
    if kind == "pivot":
        return last_pivot_low(low, pivot_left, pivot_right)
    if kind == "trade_swing":
        # Placeholder; actual level computed per-trade in simulator
        return low
    raise ValueError(f"Unknown stop kind: {kind}")


def stop_price_at_bar(
    low: pd.Series,
    kind: str,
    period: int,
    buffer_pct: float,
    pivot_left: int = 2,
    pivot_right: int = 2,
) -> pd.Series:
    level = structural_stop_level(low, kind, period, buffer_pct, pivot_left, pivot_right)
    return swing_low_with_buffer(level, buffer_pct)
