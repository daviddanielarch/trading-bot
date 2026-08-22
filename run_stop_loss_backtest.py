"""Grid backtest: top strategies × full stop-loss strategy grid."""

import json
from pathlib import Path

import pandas as pd

from backtesting.data_loader import BULL_MARKETS, load_btc_1h, slice_bull_market
from backtesting.stop_engine import run_backtest_with_stops, stop_loss_score
from backtesting.stop_loss import STOP_LOSS_GRID
from backtesting.strategies import ALL_STRATEGIES

RESULTS_DIR = Path(__file__).resolve().parent / "data" / "backtest_results"

TOP_STRATEGIES = [
    "10_Supertrend_Bull",
    "2_EMA_Cross_21_55",
    "1_EMA_Cross_12_26",
]


def main() -> None:
    df = load_btc_1h()
    strategies = [s for s in ALL_STRATEGIES if s.name in TOP_STRATEGIES]
    rows: list[dict] = []

    print("=" * 80)
    print("BACKTEST — GRID DE ESTRATEGIAS DE STOP LOSS")
    print("=" * 80)
    print(f"Estrategias: {', '.join(s.name for s in strategies)}")
    print(f"Tipos de SL: {len(STOP_LOSS_GRID)}")
    print("  % fijo, % trailing, ATR fijo/trail, chandelier, breakeven,")
    print("  estructura, time-stop")
    print()

    total_runs = len(strategies) * len(STOP_LOSS_GRID) * len(BULL_MARKETS)
    done = 0

    for period_key, (start, end) in BULL_MARKETS.items():
        period_df = slice_bull_market(df, period_key)
        warmup_start = pd.Timestamp(start, tz="UTC") - pd.Timedelta(days=30)
        warmup_df = df.loc[warmup_start:pd.Timestamp(end, tz="UTC")]

        for strategy in strategies:
            signal = strategy.generate_signals(warmup_df).loc[period_df.index]
            for sl in STOP_LOSS_GRID:
                r = run_backtest_with_stops(
                    period_df, signal, strategy.name, period_key, sl
                )
                rows.append(
                    {
                        "strategy": strategy.name,
                        "stop_loss": r.stop_config,
                        "stop_kind": sl.kind,
                        "period": period_key,
                        "return_pct": r.total_return_pct,
                        "max_dd_pct": r.max_drawdown_pct,
                        "sharpe": r.sharpe_ratio,
                        "pf": r.profit_factor,
                        "win_rate_pct": r.win_rate_pct,
                        "trades": r.num_trades,
                        "stop_exits": r.stop_exits,
                    }
                )
                done += 1
        print(f"  {period_key}: done ({done}/{total_runs})")

    detail = pd.DataFrame(rows)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    detail.to_csv(RESULTS_DIR / "stop_loss_grid_detail.csv", index=False)

    agg = (
        detail.groupby(["strategy", "stop_loss", "stop_kind"])
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

    agg["score"] = agg.apply(
        lambda r: (
            r["avg_return"] * 0.25
            + r["avg_sharpe"] * 12 * 0.35
            + min(r["avg_pf"], 5) * 4 * 0.15
            - abs(r["avg_dd"]) * 0.30
        ),
        axis=1,
    )
    agg = agg.round(2).sort_values("score", ascending=False)
    agg.to_csv(RESULTS_DIR / "stop_loss_grid_ranking.csv", index=False)

    # Best by category per strategy
    categories = {
        "pct_fijo": lambda k: k == "fixed_pct",
        "pct_trail": lambda k: k == "trail_pct",
        "atr": lambda k: k in ("atr_fixed", "atr_trail", "chandelier"),
        "breakeven": lambda k: k == "breakeven",
        "estructura": lambda k: k in (
            "fixed_swing", "trail_swing", "break_low", "entry_low", "trade_swing"
        ),
        "time": lambda k: k == "time_stop",
    }

    print()
    print("=" * 80)
    print("MEJOR SL POR CATEGORÍA (Supertrend)")
    print("=" * 80)
    st = agg[agg["strategy"] == "10_Supertrend_Bull"]
    baseline = st[st["stop_loss"] == "sin_SL"].iloc[0]
    print(
        f"Baseline sin_SL: ret {baseline['avg_return']:.1f}% | DD {baseline['avg_dd']:.1f}% | "
        f"Sharpe {baseline['avg_sharpe']:.2f}"
    )
    print()

    for cat, fn in categories.items():
        sub = st[st["stop_kind"].apply(fn)].sort_values("score", ascending=False)
        if len(sub):
            best = sub.iloc[0]
            dd_delta = best["avg_dd"] - baseline["avg_dd"]
            print(
                f"  {cat:12s} → {best['stop_loss']:20s} | ret {best['avg_return']:7.1f}% | "
                f"DD {best['avg_dd']:6.1f}% ({dd_delta:+.1f}) | Sharpe {best['avg_sharpe']:.2f} | "
                f"stops {int(best['total_stop_exits'])}"
            )

    print()
    print("=" * 80)
    print("TOP 20 COMBINACIONES GLOBALES (score risk-adjusted)")
    print("=" * 80)
    top = agg.head(20)
    print(
        top[
            ["strategy", "stop_loss", "stop_kind", "avg_return", "avg_dd", "avg_sharpe", "score"]
        ].to_string(index=False)
    )

    best = agg.iloc[0]
    print()
    print("=" * 80)
    print(f"MEJOR GLOBAL: {best['strategy']} + {best['stop_loss']}")
    print(
        f"  Retorno: {best['avg_return']}% | DD: {best['avg_dd']}% | Sharpe: {best['avg_sharpe']}"
    )
    print("=" * 80)

    with open(RESULTS_DIR / "stop_loss_grid_report.json", "w") as f:
        json.dump(
            {
                "best_global": best.to_dict(),
                "baseline_supertrend": baseline.to_dict(),
                "top20": top.to_dict(orient="records"),
                "grid_size": len(STOP_LOSS_GRID),
            },
            f,
            indent=2,
        )

    print(f"\nResultados: {RESULTS_DIR}/stop_loss_grid_*.csv")


if __name__ == "__main__":
    main()
