"""Quick test for YahooFinanceProvider — fetches a few bars for AAPL.

Usage:
    cd backend && uv run python -m scripts.test_yahoo_provider
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.ingestion.providers.yahoo import YahooFinanceProvider


async def main() -> None:
    provider = YahooFinanceProvider()
    print(f"Provider: {provider.name}\n")

    for symbol in ["AAPL", "MSFT"]:
        for interval in ["1h", "1d"]:
            print(f"--- {symbol} / {interval} ---")
            try:
                bars = await provider.fetch_ohlcv(symbol, interval, limit=5)
                print(f"  Bars returned: {len(bars)}")
                if bars:
                    last = bars[-1]
                    print(f"  Latest bar: time={last.time}, O={last.open:.2f}, "
                          f"H={last.high:.2f}, L={last.low:.2f}, C={last.close:.2f}, "
                          f"V={last.volume:.0f}")
                else:
                    print("  No bars returned (market may be closed or symbol invalid)")
            except Exception as e:
                print(f"  ERROR: {e}")
            print()

    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
