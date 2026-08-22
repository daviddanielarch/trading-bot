"""Unified stop-loss strategies: %, ATR, trailing, chandelier, breakeven, structure."""

from dataclasses import dataclass

import numpy as np
import pandas as pd

from backtesting.indicators import atr
from backtesting.market_structure import stop_price_at_bar


@dataclass(frozen=True)
class StopLossConfig:
    name: str
    kind: str  # none | fixed_pct | trail_pct | atr_fixed | atr_trail | chandelier | breakeven | ...
    pct: float = 0.0
    atr_mult: float = 2.0
    atr_period: int = 14
    period: int = 20
    buffer_pct: float = 0.5
    trigger_pct: float = 5.0
    max_bars: int = 72

    def label(self) -> str:
        return "sin_SL" if self.kind == "none" else self.name


def build_stop_loss_grid() -> list[StopLossConfig]:
    grid: list[StopLossConfig] = [StopLossConfig("sin_SL", "none")]

    for pct in (3, 5, 8, 10, 12, 15, 20):
        grid.append(StopLossConfig(f"fixed_{pct}pct", "fixed_pct", pct=pct))

    for pct in (5, 8, 10, 12, 15, 20):
        grid.append(StopLossConfig(f"trail_{pct}pct", "trail_pct", pct=pct))

    for mult in (1.5, 2.0, 2.5, 3.0, 4.0):
        grid.append(
            StopLossConfig(f"atr_fix_{mult}x", "atr_fixed", atr_mult=mult, atr_period=14)
        )

    for mult in (2.0, 2.5, 3.0, 4.0):
        grid.append(
            StopLossConfig(f"atr_trail_{mult}x", "atr_trail", atr_mult=mult, atr_period=14)
        )

    for mult in (2.0, 3.0):
        grid.append(
            StopLossConfig(f"chandelier_{mult}x", "chandelier", atr_mult=mult, atr_period=22)
        )

    for trigger in (5, 8, 10):
        grid.append(
            StopLossConfig(f"breakeven_{trigger}pct", "breakeven", trigger_pct=trigger, buffer_pct=0.2)
        )

    # Estructura (subset representativo)
    grid.extend(
        [
            StopLossConfig("fix_low20_b0.5", "fixed_swing", period=20, buffer_pct=0.5),
            StopLossConfig("trail_low20_b0.5", "trail_swing", period=20, buffer_pct=0.5),
            StopLossConfig("break_low5", "break_low", period=5),
            StopLossConfig("entry_low_b0.5", "entry_low", period=1, buffer_pct=0.5),
            StopLossConfig("trade_low_b0.5", "trade_swing", buffer_pct=0.5),
        ]
    )

    for hours in (48, 72, 120):
        grid.append(StopLossConfig(f"time_{hours}h", "time_stop", max_bars=hours))

    return grid


STOP_LOSS_GRID = build_stop_loss_grid()


def apply_stop_loss(
    df: pd.DataFrame,
    signal_position: pd.Series,
    config: StopLossConfig,
) -> tuple[pd.Series, pd.Series]:
    """Apply stop overlay; returns (position, exit_reason per bar)."""
    if config.kind == "none":
        pos = signal_position.reindex(df.index).fillna(0).astype(int)
        return pos, pd.Series("", index=df.index)

    high = df["High"]
    low = df["Low"]
    close = df["Close"]
    signal = signal_position.reindex(df.index).fillna(0).astype(int)
    atr_vals = atr(high, low, close, config.atr_period)

    structural_kinds = {
        "fixed_swing",
        "trail_swing",
        "break_low",
        "entry_low",
        "trade_swing",
    }
    if config.kind in structural_kinds:
        return _apply_structural(df, signal, config)

    n = len(df)
    position = np.zeros(n, dtype=int)
    reasons = np.empty(n, dtype="U8")
    reasons[:] = ""

    in_pos = False
    entry_price = 0.0
    entry_bar = 0
    stop_price = np.nan
    trade_high = np.nan
    breakeven_active = False

    for i in range(n):
        sig = signal.iloc[i]
        bar_low = low.iloc[i]
        bar_high = high.iloc[i]
        bar_close = close.iloc[i]
        bar_atr = atr_vals.iloc[i]

        if in_pos:
            trade_high = max(trade_high, bar_high)
            bars_held = i - entry_bar

            stop_price = _update_stop(
                config,
                entry_price,
                stop_price,
                trade_high,
                bar_atr,
                breakeven_active,
            )

            if config.kind == "breakeven" and not breakeven_active:
                gain_pct = (bar_high / entry_price - 1) * 100
                if gain_pct >= config.trigger_pct:
                    breakeven_active = True
                    stop_price = max(stop_price, entry_price * (1 + config.buffer_pct / 100))

            if config.kind == "time_stop" and bars_held >= config.max_bars:
                profit_pct = (bar_close / entry_price - 1) * 100
                if profit_pct <= 0:
                    in_pos = False
                    reasons[i] = "stop"
                    continue

            hit_stop = not np.isnan(stop_price) and bar_low <= stop_price
            sig_exit = sig == 0

            if hit_stop:
                in_pos = False
                reasons[i] = "stop"
            elif sig_exit:
                in_pos = False
                reasons[i] = "signal"
            else:
                position[i] = 1
        else:
            if sig == 1:
                in_pos = True
                position[i] = 1
                entry_price = bar_close
                entry_bar = i
                trade_high = bar_high
                breakeven_active = False
                stop_price = _initial_stop(config, entry_price, bar_atr, low.iloc[i])

    return pd.Series(position, index=df.index), pd.Series(reasons, index=df.index)


def _initial_stop(
    config: StopLossConfig,
    entry: float,
    bar_atr: float,
    entry_low: float,
) -> float:
    if config.kind == "fixed_pct":
        return entry * (1 - config.pct / 100)
    if config.kind == "trail_pct":
        return entry * (1 - config.pct / 100)
    if config.kind in ("atr_fixed", "chandelier", "atr_trail"):
        dist = config.atr_mult * bar_atr if not np.isnan(bar_atr) else entry * 0.05
        return entry - dist
    if config.kind == "breakeven":
        return entry * (1 - max(config.pct, 8) / 100)  # initial wide stop 8% default
    return np.nan


def _update_stop(
    config: StopLossConfig,
    entry: float,
    stop_price: float,
    trade_high: float,
    bar_atr: float,
    breakeven_active: bool,
) -> float:
    if config.kind == "fixed_pct":
        return entry * (1 - config.pct / 100)

    if config.kind == "trail_pct":
        new_stop = trade_high * (1 - config.pct / 100)
        return max(stop_price, new_stop) if not np.isnan(stop_price) else new_stop

    if config.kind == "atr_fixed":
        dist = config.atr_mult * bar_atr if not np.isnan(bar_atr) else entry * 0.05
        return entry - dist

    if config.kind in ("atr_trail", "chandelier"):
        dist = config.atr_mult * bar_atr if not np.isnan(bar_atr) else entry * 0.05
        new_stop = trade_high - dist
        return max(stop_price, new_stop) if not np.isnan(stop_price) else new_stop

    if config.kind == "breakeven":
        base = entry * (1 - 8 / 100)
        if breakeven_active:
            be = entry * (1 + config.buffer_pct / 100)
            return max(stop_price, be) if not np.isnan(stop_price) else be
        return stop_price if not np.isnan(stop_price) else base

    return stop_price


def _apply_structural(
    df: pd.DataFrame,
    signal: pd.Series,
    config: StopLossConfig,
) -> tuple[pd.Series, pd.Series]:
    low = df["Low"]
    close = df["Close"]
    kind = config.kind
    ref_kind = "trail_swing" if kind == "break_low" else kind

    ref_stop = stop_price_at_bar(
        low,
        ref_kind if kind != "trade_swing" else "trade_swing",
        config.period,
        config.buffer_pct,
    )

    n = len(df)
    position = np.zeros(n, dtype=int)
    reasons = np.empty(n, dtype="U8")
    reasons[:] = ""

    in_pos = False
    stop_price = np.nan
    trade_low = np.nan
    trail = kind == "trail_swing"
    trade_sw = kind == "trade_swing"
    break_k = kind == "break_low"

    for i in range(n):
        sig = signal.iloc[i]
        bar_low = low.iloc[i]
        bar_close = close.iloc[i]

        if in_pos:
            if trade_sw:
                trade_low = min(trade_low, bar_low)
                stop_price = trade_low * (1 - config.buffer_pct / 100)
            elif trail:
                if not np.isnan(ref_stop.iloc[i]):
                    stop_price = ref_stop.iloc[i]
            elif break_k:
                level = ref_stop.iloc[i]
                if not np.isnan(level) and bar_close < level:
                    in_pos = False
                    reasons[i] = "stop"
                    continue

            hit = not np.isnan(stop_price) and bar_low <= stop_price
            if hit:
                in_pos = False
                reasons[i] = "stop"
            elif sig == 0:
                in_pos = False
                reasons[i] = "signal"
            else:
                position[i] = 1
        elif sig == 1:
            in_pos = True
            position[i] = 1
            trade_low = bar_low
            if trade_sw:
                stop_price = trade_low * (1 - config.buffer_pct / 100)
            else:
                stop_price = ref_stop.iloc[i]
            if np.isnan(stop_price):
                stop_price = bar_low * (1 - config.buffer_pct / 100)

    return pd.Series(position, index=df.index), pd.Series(reasons, index=df.index)
