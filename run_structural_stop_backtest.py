"""Grid backtest: strategies × structural stop-loss combinations."""

import json
from pathlib import Path

import pandas as pd

from backtesting.data_loader import BULL_MARKETS, load_btc_1h, slice_bull_market
from backtesting.structural_engine import run_backtest_structural, structural_composite_score
from backtesting.structural_stops import STRUCTURAL_STOP_GRID
from backtesting.strategies import ALL_STRATEGIES

RESULTS_DIR = Path(__file__).resolve().parent / "data" / "backtest_results"

# Focus on top performers + representative set; grid is large if all 10 × 15
TOP_STRATEGIES = [
    "10_Supertrend_Bull",
    "2_EMA_Cross_21_55",
    "1_EMA_Cross_12_26",
    "6_BB_Squeeze_Break",
]


def main() -> None:
    df = load_btc_1h()
    strategies = [s for s in ALL_STRATEGIES if s.name in TOP_STRATEGIES]
    all_results: list = []

    print("=" * 80)
    print("BACKTEST — STOP LOSS ESTRUCTURAL (soportes / mínimos)")
    print("=" * 80)
    print(f"Estrategias: {', '.join(s.name for s in strategies)}")
    print(f"Combinaciones SL: {len(STRUCTURAL_STOP_GRID)}")
    print()

    for period_key, (start, end) in BULL_MARKETS.items():
        period_df = slice_bull_market(df, period_key)
        warmup_start = pd.Timestamp(start, tz="UTC") - pd.Timedelta(days=30)
        warmup_df = df.loc[warmup_start:pd.Timestamp(end, tz="UTC")]
        print(f"--- {period_key} ---")

        for strategy in strategies:
            signal_full = strategy.generate_signals(warmup_df)
            signal = signal_full.loc[period_df.index]

            for stop_cfg in STRUCTURAL_STOP_GRID:
                result = run_backtest_structural(
                    period_df,
                    signal,
                    strategy.name,
                    period_key,
                    stop_cfg,
                )
                all_results.append(result)

        print(f"  {len(strategies) * len(STRUCTURAL_STOP_GRID)} runs completados")
    print()

    rows = []
    for r in all_results:
        rows.append(
            {
                "strategy": r.strategy_name.split("|")[0],
                "stop_config": r.stop_config,
                "period": r.period,
                "return_pct": r.total_return_pct,
                "buy_hold_pct": r.buy_hold_return_pct,
                "max_dd_pct": r.max_drawdown_pct,
                "sharpe": r.sharpe_ratio,
                "pf": r.profit_factor,
                "win_rate_pct": r.win_rate_pct,
                "trades": r.num_trades,
                "stop_exits": r.stop_exits,
                "signal_exits": r.signal_exits,
                "time_in_market_pct": r.time_in_market_pct,
            }
        )

    detail = pd.DataFrame(rows)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    detail.to_csv(RESULTS_DIR / "structural_stop_detail.csv", index=False)

    # Aggregate by strategy + stop across both bull markets
    agg = (
        detail.groupby(["strategy", "stop_config"])
        .agg(
            avg_return=("return_pct", "mean"),
            avg_dd=("max_dd_pct", "mean"),
            avg_sharpe=("sharpe", "mean"),
            avg_pf=("pf", "mean"),
            total_trades=("trades", "sum"),
            total_stop_exits=("stop_exits", "sum"),
        )
        .reset_index()
    )

    # Score rows
    agg["composite"] = agg.apply(
        lambda row: (
            row["avg_return"] * 0.30
            + row["avg_sharpe"] * 10 * 0.30
            + min(row["avg_pf"], 5) * 4 * 0.15
            - abs(row["avg_dd"]) * 0.25
        ),
        axis=1,
    )
    agg = agg.round(2).sort_values("composite", ascending=False)

    agg.to_csv(RESULTS_DIR / "structural_stop_ranking.csv", index=False)

    # Best per strategy vs baseline (sin_SL)
    print("=" * 80)
    print("MEJOR SL POR ESTRATEGIA (vs sin SL)")
    print("=" * 80)
    for strat in TOP_STRATEGIES:
        sub = agg[agg["strategy"] == strat].sort_values("composite", ascending=False)
        baseline = sub[sub["stop_config"] == "sin_SL"].iloc[0]
        best = sub.iloc[0]
        print(f"\n{strat}:")
        print(
            f"  sin_SL     → ret {baseline['avg_return']:>7.1f}% | DD {baseline['avg_dd']:>6.1f}% | "
            f"Sharpe {baseline['avg_sharpe']:.2f} | trades {int(baseline['total_trades'])}"
        )
        if best["stop_config"] != "sin_SL":
            print(
                f"  MEJOR: {best['stop_config']:16s} → ret {best['avg_return']:>7.1f}% | "
                f"DD {best['avg_dd']:>6.1f}% | Sharpe {best['avg_sharpe']:.2f} | "
                f"stop exits {int(best['total_stop_exits'])}"
            )
        else:
            print("  MEJOR: sin_SL (ningún SL estructural supera baseline)")

    print()
    print("=" * 80)
    print("TOP 15 COMBINACIONES GLOBALES")
    print("=" * 80)
    print(
        agg.head(15)[
            ["strategy", "stop_config", "avg_return", "avg_dd", "avg_sharpe", "avg_pf", "composite"]
        ].to_string(index=False)
    )

    global_best = agg.iloc[0]
    print()
    print("=" * 80)
    print(f"MEJOR COMBINACIÓN GLOBAL: {global_best['strategy']} + {global_best['stop_config']}")
    print(
        f"  Retorno medio: {global_best['avg_return']}% | Max DD: {global_best['avg_dd']}% | "
        f"Sharpe: {global_best['avg_sharpe']} | PF: {global_best['avg_pf']}"
    )
    print("=" * 80)

    report = {
        "top_global": global_best.to_dict(),
        "stop_grid": [c.name for c in STRUCTURAL_STOP_GRID],
        "ranking_top15": agg.head(15).to_dict(orient="records"),
    }
    with open(RESULTS_DIR / "structural_stop_report.json", "w") as f:
        json.dump(report, f, indent=2)

    print(f"\nResultados en {RESULTS_DIR}/structural_stop_*.csv")


if __name__ == "__main__":
    main()
