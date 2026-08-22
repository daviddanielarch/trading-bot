"""Download BTC/USD 1h OHLCV from public sources."""

import shutil
import subprocess
import sys
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
OUTPUT = DATA_DIR / "btc_usd_1h.csv"
SOURCE_URL = (
    "https://raw.githubusercontent.com/ArdRay/bitcoin_historical/main/historical_data/bitcoin.csv"
)


def download() -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = DATA_DIR / "bitcoin_raw.csv"
    subprocess.run(
        ["curl", "-sL", SOURCE_URL, "-o", str(tmp)],
        check=True,
    )
    shutil.move(tmp, OUTPUT)
    print(f"Saved {OUTPUT}")
    return OUTPUT


if __name__ == "__main__":
    download()
