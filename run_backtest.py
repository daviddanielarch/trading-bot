"""Run backtests for all bullish 1h strategies on previous BTC bull markets."""

import json
from pathlib import Path

import pandas as pd

from backtesting.data_loader import BULL_MARKETS, load_btc_1h, slice_bull_market
from backtesting.engine import BacktestResult, composite_score, run_backtest
from backtesting.strategies import ALL_STRATEGIES


RESULTS_DIR = Path(__file__).resolve().parent / "data" / "backtest_results"


def main() -> None:
    df = load_btc_1h()
    all_results: list[BacktestResult] = []

    print("=" * 72)
    print("BACKTEST BTC 1H — ESTRATEGIAS ALCISTAS")
    print("=" * 72)
    print(f"Datos: {df.index.min()} → {df.index.max()} ({len(df):,} velas)")
    print()

    for period_key, (start, end) in BULL_MARKETS.items():
        period_df = slice_bull_market(df, period_key)
        warmup_start = pd.Timestamp(start, tz="UTC") - pd.Timedelta(days=30)
        warmup_df = df.loc[warmup_start:pd.Timestamp(end, tz="UTC")]
        print(f"--- {period_key}: {start} → {end} ({len(period_df):,} velas) ---")

        for strategy in ALL_STRATEGIES:
            position_full = strategy.generate_signals(warmup_df)
            position = position_full.loc[period_df.index]
            result = run_backtest(
                period_df,
                position,
                strategy.name,
                period_key,
            )
            all_results.append(result)
            print(
                f"  {strategy.name:28s} | ret {result.total_return_pct:>8.1f}% | "
                f"B&H {result.buy_hold_return_pct:>8.1f}% | "
                f"DD {result.max_drawdown_pct:>6.1f}% | Sharpe {result.sharpe_ratio:>5.2f} | "
                f"trades {result.num_trades:>4d}"
            )
        print()

    # Aggregate scores across both bull markets
    summary_rows = []
    for strategy in ALL_STRATEGIES:
        strat_results = [r for r in all_results if r.strategy_name == strategy.name]
        avg_return = sum(r.total_return_pct for r in strat_results) / len(strat_results)
        avg_bh = sum(r.buy_hold_return_pct for r in strat_results) / len(strat_results)
        avg_dd = sum(r.max_drawdown_pct for r in strat_results) / len(strat_results)
        avg_sharpe = sum(r.sharpe_ratio for r in strat_results) / len(strat_results)
        total_trades = sum(r.num_trades for r in strat_results)
        avg_pf = sum(r.profit_factor for r in strat_results) / len(strat_results)
        avg_win = sum(r.win_rate_pct for r in strat_results) / len(strat_results)
        composite = sum(composite_score(r) for r in strat_results) / len(strat_results)

        summary_rows.append(
            {
                "strategy": strategy.name,
                "description": strategy.description,
                "avg_return_pct": round(avg_return, 2),
                "avg_buy_hold_pct": round(avg_bh, 2),
                "avg_excess_pct": round(avg_return - avg_bh, 2),
                "avg_max_dd_pct": round(avg_dd, 2),
                "avg_sharpe": round(avg_sharpe, 2),
                "total_trades": total_trades,
                "avg_profit_factor": round(avg_pf, 2),
                "avg_win_rate_pct": round(avg_win, 2),
                "composite_score": round(composite, 2),
            }
        )

    summary = pd.DataFrame(summary_rows).sort_values("composite_score", ascending=False)

    # Risk-adjusted ranking (Sharpe-focused for bull market active trading)
    risk_adj = summary.sort_values("avg_sharpe", ascending=False)

    best = summary.iloc[0]
    best_sharpe = risk_adj.iloc[0]

    print("=" * 72)
    print("RANKING COMBINADO (ambos bull markets)")
    print("=" * 72)
    print(summary.to_string(index=False))
    print()
    print("=" * 72)
    print(f"MEJOR ESTRATEGIA (score compuesto): {best['strategy']}")
    print(f"  {best['description']}")
    print(f"  Retorno medio: {best['avg_return_pct']}% | Exceso vs B&H: {best['avg_excess_pct']}%")
    print(f"  Sharpe medio: {best['avg_sharpe']} | Max DD medio: {best['avg_max_dd_pct']}%")
    print(f"  Profit factor: {best['avg_profit_factor']} | Win rate: {best['avg_win_rate_pct']}%")
    print()
    print(f"MEJOR RISK-ADJUSTED (Sharpe): {best_sharpe['strategy']}")
    print(f"  Sharpe: {best_sharpe['avg_sharpe']} | Retorno: {best_sharpe['avg_return_pct']}%")
    print("=" * 72)
    print("NOTA: En bull markets extremos, Buy & Hold suele superar estrategias activas")
    print(f"       en retorno bruto (B&H medio: {best['avg_buy_hold_pct']}%).")
    print("       Las estrategias activas reducen drawdown y ofrecen gestión de riesgo.")
    print("=" * 72)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    summary.to_csv(RESULTS_DIR / "strategy_ranking.csv", index=False)

    detail = pd.DataFrame([vars(r) for r in all_results])
    detail.to_csv(RESULTS_DIR / "backtest_detail.csv", index=False)

    report = {
        "best_strategy_composite": best["strategy"],
        "best_strategy_sharpe": best_sharpe["strategy"],
        "best_description": best["description"],
        "bull_markets": BULL_MARKETS,
        "fee_pct": 0.1,
        "ranking": summary_rows,
    }
    with open(RESULTS_DIR / "report.json", "w") as f:
        json.dump(report, f, indent=2)

    print(f"\nResultados guardados en {RESULTS_DIR}")


if __name__ == "__main__":
    main()
