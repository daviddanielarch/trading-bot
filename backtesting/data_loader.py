"""Load and normalize BTC/USD 1-hour OHLCV data."""

from pathlib import Path
import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DEFAULT_CSV = DATA_DIR / "btc_usd_1h.csv"

BULL_MARKETS = {
    "bull_2016_2017": ("2016-01-01", "2017-12-17"),
    "bull_2020_2021": ("2020-10-01", "2021-11-10"),
}


def _utc(ts: str) -> pd.Timestamp:
    return pd.Timestamp(ts, tz="UTC")


def load_btc_1h(csv_path: Path | None = None) -> pd.DataFrame:
    path = csv_path or DEFAULT_CSV
    if not path.exists():
        raise FileNotFoundError(
            f"BTC data not found at {path}. Run scripts/download_btc_data.py first."
        )

    df = pd.read_csv(path)
    if "date" in df.columns:
        df["timestamp"] = pd.to_datetime(df["date"], utc=True)
    elif "Date" in df.columns:
        df["timestamp"] = pd.to_datetime(df["Date"], utc=True)
    else:
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)

    column_map = {
        "open": "Open",
        "high": "High",
        "low": "Low",
        "close": "Close",
        "volume": "Volume",
    }
    for lower, upper in column_map.items():
        if lower in df.columns and upper not in df.columns:
            df[upper] = df[lower]

    required = ["Open", "High", "Low", "Close"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing columns: {missing}")

    if "Volume" not in df.columns:
        df["Volume"] = 0.0

    df = df.sort_values("timestamp").drop_duplicates("timestamp")
    df = df.set_index("timestamp")
    return df[["Open", "High", "Low", "Close", "Volume"]].astype(float)


def slice_bull_market(df: pd.DataFrame, period_key: str) -> pd.DataFrame:
    start, end = BULL_MARKETS[period_key]
    return df.loc[_utc(start):_utc(end)].copy()
