"""Yahoo Finance market data provider — delayed OHLCV for stocks.

Uses the `yfinance` library (unofficial Yahoo Finance API wrapper).
Since yfinance is synchronous, all calls are wrapped with asyncio.to_thread().

Limitations:
- Data is delayed ~15 minutes for US stocks.
- 1h interval: max ~730 days of history.
- 1d interval: max ~10 years of history.
- No official rate limits, but aggressive polling may trigger temporary blocks.
- Weekend/holiday gaps are normal for stocks (no bars outside trading hours).
"""

import asyncio
from datetime import datetime, timedelta, timezone

import yfinance as yf

from app.logging_config import get_logger

from .base import BaseProvider, RawBar

log = get_logger(__name__)

# yfinance interval mapping
INTERVAL_MAP = {
    "1h": "1h",
    "1d": "1d",
}


class YahooFinanceProvider(BaseProvider):
    """Fetches OHLCV from Yahoo Finance for stocks (and other instruments)."""

    @property
    def name(self) -> str:
        return "yahoo_finance"

    async def fetch_ohlcv(
        self,
        symbol: str,
        interval: str,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 1000,
    ) -> list[RawBar]:
        yf_interval = INTERVAL_MAP.get(interval)
        if not yf_interval:
            raise ValueError(
                f"Unsupported Yahoo Finance interval: {interval}. "
                f"Supported: {', '.join(INTERVAL_MAP.keys())}"
            )

        # yfinance uses period OR start/end — we prefer start/end for consistency
        now = datetime.now(timezone.utc)
        start = start_time or (now - timedelta(days=7))
        end = end_time or now

        log.debug(
            "yahoo_request",
            symbol=symbol,
            interval=interval,
            start=str(start),
            end=str(end),
        )

        # yfinance is synchronous — run in thread pool
        bars = await asyncio.to_thread(
            self._fetch_sync, symbol, yf_interval, start, end
        )

        # Respect limit
        if len(bars) > limit:
            bars = bars[-limit:]

        log.debug("yahoo_response", symbol=symbol, bars_count=len(bars))
        return bars

    @staticmethod
    def _fetch_sync(
        symbol: str,
        interval: str,
        start: datetime,
        end: datetime,
    ) -> list[RawBar]:
        """Synchronous fetch using yfinance. Runs in a thread."""
        ticker = yf.Ticker(symbol)

        # yfinance expects string dates or datetime objects
        df = ticker.history(
            interval=interval,
            start=start,
            end=end,
            auto_adjust=True,  # Adjusted OHLC (splits/dividends)
            prepost=False,  # Regular trading hours only
        )

        if df is None or df.empty:
            return []

        bars = []
        for idx, row in df.iterrows():
            # idx is a pandas Timestamp (timezone-aware for intraday)
            bar_time = idx.to_pydatetime()
            if bar_time.tzinfo is None:
                bar_time = bar_time.replace(tzinfo=timezone.utc)
            else:
                bar_time = bar_time.astimezone(timezone.utc)

            # Skip rows with zero volume (can happen for some tickers)
            volume = float(row.get("Volume", 0))

            bars.append(
                RawBar(
                    time=bar_time,
                    open=float(row["Open"]),
                    high=float(row["High"]),
                    low=float(row["Low"]),
                    close=float(row["Close"]),
                    volume=volume,
                )
            )

        return bars
