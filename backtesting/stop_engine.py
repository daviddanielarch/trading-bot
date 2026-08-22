"""Backtest engine with any stop-loss strategy."""

from dataclasses import dataclass

import numpy as np
import pandas as pd

from backtesting.engine import BacktestResult, composite_score
from backtesting.stop_loss import StopLossConfig, apply_stop_loss


@dataclass
class StopLossBacktestResult(BacktestResult):
    stop_config: str = ""
    stop_exits: int = 0
    signal_exits: int = 0


def run_backtest_with_stops(
    df: pd.DataFrame,
    signal_position: pd.Series,
    strategy_name: str,
    period: str,
    stop_config: StopLossConfig,
    fee_pct: float = 0.1,
    initial_capital: float = 10000.0,
) -> StopLossBacktestResult:
    actual_pos, exit_reasons = apply_stop_loss(df, signal_position, stop_config)

    low = df["Low"].values
    close = df["Close"].values
    n = len(df)

    equity = initial_capital
    equity_curve = np.empty(n)
    hourly_rets = np.zeros(n)

    entry_price = 0.0
    trade_rets: list[float] = []
    stop_exits = 0
    signal_exits = 0

    for i in range(n):
        prev_pos = actual_pos.iloc[i - 1] if i > 0 else 0
        curr_pos = actual_pos.iloc[i]

        if i > 0 and prev_pos == 1:
            if curr_pos == 1:
                hourly_rets[i] = (close[i] / close[i - 1]) - 1
            else:
                reason = exit_reasons.iloc[i]
                if reason == "stop":
                    exit_price = low[i]
                    hourly_rets[i] = (exit_price / close[i - 1]) - 1
                    stop_exits += 1
                    if entry_price > 0:
                        trade_rets.append((exit_price / entry_price) - 1)
                else:
                    hourly_rets[i] = (close[i] / close[i - 1]) - 1
                    if reason == "signal":
                        signal_exits += 1
                    if entry_price > 0:
                        trade_rets.append((close[i] / entry_price) - 1)
                entry_price = 0.0
        elif i > 0 and prev_pos == 0 and curr_pos == 1:
            hourly_rets[i] = 0.0
            entry_price = close[i]
        elif i > 0 and prev_pos == 0 and curr_pos == 0:
            hourly_rets[i] = 0.0

        if i > 0 and prev_pos != curr_pos:
            hourly_rets[i] -= fee_pct / 100.0

        equity *= 1 + hourly_rets[i]
        equity_curve[i] = equity

    if actual_pos.iloc[-1] == 1 and entry_price > 0:
        trade_rets.append((close[-1] / entry_price) - 1)

    returns = pd.Series(close).pct_change().fillna(0)
    buy_hold = initial_capital * (1 + returns).cumprod()
    total_return = (equity / initial_capital - 1) * 100
    buy_hold_return = (buy_hold.iloc[-1] / initial_capital - 1) * 100

    eq_series = pd.Series(equity_curve, index=df.index)
    max_dd = ((eq_series - eq_series.cummax()) / eq_series.cummax()).min() * 100

    net_returns = pd.Series(hourly_rets, index=df.index)
    sharpe = (
        (net_returns.mean() / net_returns.std()) * np.sqrt(24 * 365)
        if net_returns.std() > 0
        else 0.0
    )

    trade_arr = np.array(trade_rets)
    num_trades = len(trade_arr)
    if num_trades > 0:
        wins = trade_arr[trade_arr > 0]
        losses = trade_arr[trade_arr <= 0]
        win_rate = len(wins) / num_trades * 100
        gp = wins.sum() if len(wins) else 0
        gl = abs(losses.sum()) if len(losses) else 0
        pf = gp / gl if gl > 0 else float("inf")
        avg_trade = trade_arr.mean() * 100
    else:
        win_rate = 0.0
        pf = 0.0
        avg_trade = 0.0

    return StopLossBacktestResult(
        strategy_name=f"{strategy_name}|{stop_config.label()}",
        period=period,
        total_return_pct=round(total_return, 2),
        buy_hold_return_pct=round(buy_hold_return, 2),
        max_drawdown_pct=round(max_dd, 2),
        sharpe_ratio=round(sharpe, 2),
        win_rate_pct=round(win_rate, 2),
        num_trades=num_trades,
        profit_factor=round(pf, 2) if pf != float("inf") else 999.99,
        avg_trade_return_pct=round(avg_trade, 2),
        time_in_market_pct=round(actual_pos.mean() * 100, 2),
        stop_config=stop_config.label(),
        stop_exits=stop_exits,
        signal_exits=signal_exits,
    )


def stop_loss_score(result: StopLossBacktestResult) -> float:
    """Risk-adjusted score prioritizing Sharpe and drawdown control."""
    pf = min(result.profit_factor, 5.0)
    return (
        result.total_return_pct * 0.25
        + result.sharpe_ratio * 12 * 0.35
        + pf * 4 * 0.15
        - abs(result.max_drawdown_pct) * 0.30
    )
