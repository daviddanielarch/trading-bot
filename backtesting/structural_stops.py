"""Structural stop-loss configurations and position simulation."""

from dataclasses import dataclass

import numpy as np
import pandas as pd

from backtesting.market_structure import stop_price_at_bar


@dataclass(frozen=True)
class StructuralStopConfig:
    name: str
    kind: str  # fixed_swing | trail_swing | trail_ratchet | entry_low | pivot | trade_swing | break_low | none
    period: int = 20
    buffer_pct: float = 0.5
    pivot_left: int = 2
    pivot_right: int = 2

    def label(self) -> str:
        if self.kind == "none":
            return "sin_SL"
        return self.name


# Curated combinations — includes tight structure (3–8 bars) and trade swing lows
STRUCTURAL_STOP_GRID: list[StructuralStopConfig] = [
    StructuralStopConfig("sin_SL", "none"),
    # Tight fixed support (minimos recientes al entrar)
    StructuralStopConfig("fix_low3_b0.5", "fixed_swing", period=3, buffer_pct=0.5),
    StructuralStopConfig("fix_low5_b0.5", "fixed_swing", period=5, buffer_pct=0.5),
    StructuralStopConfig("fix_low5_b1", "fixed_swing", period=5, buffer_pct=1.0),
    StructuralStopConfig("fix_low8_b0.5", "fixed_swing", period=8, buffer_pct=0.5),
    StructuralStopConfig("fix_low10_b0.5", "fixed_swing", period=10, buffer_pct=0.5),
    StructuralStopConfig("fix_low20_b0.5", "fixed_swing", period=20, buffer_pct=0.5),
    StructuralStopConfig("fix_low50_b0.5", "fixed_swing", period=50, buffer_pct=0.5),
    # Trailing bajo minimo rolling (periodos cortos y largos)
    StructuralStopConfig("trail_low3_b0.5", "trail_swing", period=3, buffer_pct=0.5),
    StructuralStopConfig("trail_low5_b0.5", "trail_swing", period=5, buffer_pct=0.5),
    StructuralStopConfig("trail_low8_b0.5", "trail_swing", period=8, buffer_pct=0.5),
    StructuralStopConfig("trail_low10_b0.5", "trail_swing", period=10, buffer_pct=0.5),
    StructuralStopConfig("trail_low20_b0.5", "trail_swing", period=20, buffer_pct=0.5),
    # Minimo desde la entrada (estructura del trade)
    StructuralStopConfig("trade_low_b0.5", "trade_swing", period=0, buffer_pct=0.5),
    StructuralStopConfig("trade_low_b1", "trade_swing", period=0, buffer_pct=1.0),
    # Low de vela de entrada
    StructuralStopConfig("entry_low_b0.5", "entry_low", period=1, buffer_pct=0.5),
    StructuralStopConfig("entry_low_b1", "entry_low", period=1, buffer_pct=1.0),
    # Pivot / swing confirmado
    StructuralStopConfig("pivot_b0.5", "pivot", period=0, buffer_pct=0.5, pivot_left=2, pivot_right=2),
    StructuralStopConfig("pivot_b1", "pivot", period=0, buffer_pct=1.0, pivot_left=2, pivot_right=2),
    # Break of structure: cierre rompe minimo N velas
    StructuralStopConfig("break_low3", "break_low", period=3, buffer_pct=0.0),
    StructuralStopConfig("break_low5", "break_low", period=5, buffer_pct=0.0),
    StructuralStopConfig("break_low8", "break_low", period=8, buffer_pct=0.0),
    # Ratchet: SL solo sube cuando el soporte estructural sube
    StructuralStopConfig("ratchet_low8_b0.5", "trail_ratchet", period=8, buffer_pct=0.5),
    StructuralStopConfig("ratchet_low20_b0.5", "trail_ratchet", period=20, buffer_pct=0.5),
    StructuralStopConfig("ratchet_low20_b1", "trail_ratchet", period=20, buffer_pct=1.0),
]


def apply_structural_stops(
    df: pd.DataFrame,
    signal_position: pd.Series,
    stop_config: StructuralStopConfig,
) -> tuple[pd.Series, pd.Series]:
    """
    Overlay structural stops on strategy signals.

    Returns:
        actual_position: 1 when long, 0 when flat (after stops)
        exit_reason: 'signal' | 'stop' | '' per bar
    """
    if stop_config.kind == "none":
        pos = signal_position.reindex(df.index).fillna(0).astype(int)
        reasons = pd.Series("", index=df.index)
        return pos, reasons

    low = df["Low"]
    close = df["Close"]
    signal = signal_position.reindex(df.index).fillna(0).astype(int)

    ref_stop = stop_price_at_bar(
        low,
        "trail_swing" if stop_config.kind in ("trail_swing", "trail_ratchet", "break_low") else stop_config.kind,
        stop_config.period,
        stop_config.buffer_pct,
        stop_config.pivot_left,
        stop_config.pivot_right,
    )

    n = len(df)
    position = np.zeros(n, dtype=int)
    reasons = np.empty(n, dtype="U8")
    reasons[:] = ""

    in_pos = False
    stop_price = np.nan
    trade_low = np.nan
    trail_kind = stop_config.kind == "trail_swing"
    ratchet_kind = stop_config.kind == "trail_ratchet"
    trade_swing_kind = stop_config.kind == "trade_swing"
    break_kind = stop_config.kind == "break_low"

    for i in range(n):
        sig = signal.iloc[i]
        bar_low = low.iloc[i]
        bar_close = close.iloc[i]

        if in_pos:
            if trade_swing_kind:
                trade_low = min(trade_low, bar_low)
                stop_price = trade_low * (1 - stop_config.buffer_pct / 100.0)
            elif trail_kind:
                if not np.isnan(ref_stop.iloc[i]):
                    stop_price = ref_stop.iloc[i]
            elif ratchet_kind:
                if not np.isnan(ref_stop.iloc[i]):
                    stop_price = max(stop_price, ref_stop.iloc[i])
            elif break_kind:
                level = ref_stop.iloc[i]
                if not np.isnan(level) and bar_close < level:
                    in_pos = False
                    stop_price = np.nan
                    trade_low = np.nan
                    reasons[i] = "stop"
                    continue

            hit_stop = not np.isnan(stop_price) and bar_low <= stop_price
            sig_exit = sig == 0

            if hit_stop:
                in_pos = False
                stop_price = np.nan
                trade_low = np.nan
                reasons[i] = "stop"
            elif sig_exit:
                in_pos = False
                stop_price = np.nan
                trade_low = np.nan
                reasons[i] = "signal"
            else:
                position[i] = 1
        else:
            if sig == 1:
                in_pos = True
                position[i] = 1
                trade_low = bar_low
                if trade_swing_kind:
                    stop_price = trade_low * (1 - stop_config.buffer_pct / 100.0)
                elif trail_kind or break_kind or ratchet_kind:
                    stop_price = ref_stop.iloc[i]
                else:
                    stop_price = ref_stop.iloc[i]
                if np.isnan(stop_price):
                    stop_price = bar_low * (1 - stop_config.buffer_pct / 100.0)

    return pd.Series(position, index=df.index), pd.Series(reasons, index=df.index)


def count_stop_exits(exit_reasons: pd.Series) -> int:
    return int((exit_reasons == "stop").sum())
