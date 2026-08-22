"""Vectorized long-only backtest engine."""

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class BacktestResult:
    strategy_name: str
    period: str
    total_return_pct: float
    buy_hold_return_pct: float
    max_drawdown_pct: float
    sharpe_ratio: float
    win_rate_pct: float
    num_trades: int
    profit_factor: float
    avg_trade_return_pct: float
    time_in_market_pct: float


def run_backtest(
    df: pd.DataFrame,
    position: pd.Series,
    strategy_name: str,
    period: str,
    fee_pct: float = 0.1,
    initial_capital: float = 10000.0,
) -> BacktestResult:
    close = df["Close"]
    pos = position.reindex(close.index).fillna(0).astype(int)

    returns = close.pct_change().fillna(0)
    strategy_returns = pos.shift(1).fillna(0) * returns

    trades = pos.diff().fillna(0)
    trade_cost = (trades != 0).abs() * (fee_pct / 100)
    net_returns = strategy_returns - trade_cost

    equity = initial_capital * (1 + net_returns).cumprod()
    buy_hold = initial_capital * (1 + returns).cumprod()

    total_return = (equity.iloc[-1] / initial_capital - 1) * 100
    buy_hold_return = (buy_hold.iloc[-1] / initial_capital - 1) * 100

    rolling_max = equity.cummax()
    drawdown = (equity - rolling_max) / rolling_max
    max_dd = drawdown.min() * 100

    hourly_returns = net_returns
    if hourly_returns.std() > 0:
        sharpe = (hourly_returns.mean() / hourly_returns.std()) * np.sqrt(24 * 365)
    else:
        sharpe = 0.0

    trade_returns = _extract_trade_returns(close, pos)
    num_trades = len(trade_returns)
    if num_trades > 0:
        wins = trade_returns[trade_returns > 0]
        losses = trade_returns[trade_returns <= 0]
        win_rate = len(wins) / num_trades * 100
        gross_profit = wins.sum() if len(wins) else 0
        gross_loss = abs(losses.sum()) if len(losses) else 0
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")
        avg_trade = trade_returns.mean() * 100
    else:
        win_rate = 0.0
        profit_factor = 0.0
        avg_trade = 0.0

    time_in_market = pos.mean() * 100

    return BacktestResult(
        strategy_name=strategy_name,
        period=period,
        total_return_pct=round(total_return, 2),
        buy_hold_return_pct=round(buy_hold_return, 2),
        max_drawdown_pct=round(max_dd, 2),
        sharpe_ratio=round(sharpe, 2),
        win_rate_pct=round(win_rate, 2),
        num_trades=num_trades,
        profit_factor=round(profit_factor, 2) if profit_factor != float("inf") else 999.99,
        avg_trade_return_pct=round(avg_trade, 2),
        time_in_market_pct=round(time_in_market, 2),
    )


def _extract_trade_returns(close: pd.Series, position: pd.Series) -> np.ndarray:
    """Return per-trade percentage returns for completed round trips."""
    entries = []
    entry_price = None
    trade_rets = []

    for i in range(len(position)):
        prev = position.iloc[i - 1] if i > 0 else 0
        curr = position.iloc[i]
        price = close.iloc[i]

        if prev == 0 and curr == 1:
            entry_price = price
        elif prev == 1 and curr == 0 and entry_price is not None:
            trade_rets.append((price / entry_price) - 1)
            entry_price = None

    if position.iloc[-1] == 1 and entry_price is not None:
        trade_rets.append((close.iloc[-1] / entry_price) - 1)

    return np.array(trade_rets)


def composite_score(result: BacktestResult) -> float:
    """Score combining return, risk-adjusted metrics, and drawdown."""
    excess = result.total_return_pct - result.buy_hold_return_pct
    dd_penalty = abs(result.max_drawdown_pct)
    pf = min(result.profit_factor, 5.0)
    return (
        result.total_return_pct * 0.35
        + excess * 0.25
        + result.sharpe_ratio * 8 * 0.25
        + pf * 5 * 0.10
        - dd_penalty * 0.15
    )
