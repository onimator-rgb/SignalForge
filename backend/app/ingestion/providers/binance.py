"""Binance market data provider — public klines API."""

from datetime import datetime, timezone

import httpx

from app.config import settings
from app.logging_config import get_logger

from .base import BaseProvider, RawBar

log = get_logger(__name__)

# Binance interval strings that map 1:1 to our internal intervals
SUPPORTED_INTERVALS = {"1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "1d"}


class BinanceProvider(BaseProvider):
    """Fetches OHLCV from Binance public REST API (no auth required)."""

    def __init__(self, base_url: str | None = None, timeout: float = 20.0):
        self._base_url = (base_url or settings.BINANCE_BASE_URL).rstrip("/")
        self._timeout = timeout

    @property
    def name(self) -> str:
        return "binance"

    async def fetch_ohlcv(
        self,
        symbol: str,
        interval: str,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 1000,
    ) -> list[RawBar]:
        if interval not in SUPPORTED_INTERVALS:
            raise ValueError(f"Unsupported Binance interval: {interval}")

        params: dict = {
            "symbol": symbol,
            "interval": interval,
            "limit": min(limit, 1000),  # Binance hard max
        }
        if start_time:
            params["startTime"] = int(start_time.timestamp() * 1000)
        if end_time:
            params["endTime"] = int(end_time.timestamp() * 1000)

        url = f"{self._base_url}/api/v3/klines"
        log.debug(
            "binance_request",
            symbol=symbol,
            interval=interval,
            start=str(start_time),
            limit=params["limit"],
        )

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            raw = resp.json()

        bars = self._parse_klines(raw)
        log.debug("binance_response", symbol=symbol, bars_count=len(bars))
        return bars

    @staticmethod
    def _parse_klines(raw: list[list]) -> list[RawBar]:
        """Parse Binance klines response into RawBar list.

        Binance kline format (array of arrays):
        [
          [
            0: openTime (ms),
            1: open,
            2: high,
            3: low,
            4: close,
            5: volume,
            6: closeTime (ms),
            7: quoteAssetVolume,
            8: numberOfTrades,
            9: takerBuyBaseVolume,
            10: takerBuyQuoteVolume,
            11: ignore
          ]
        ]
        """
        bars = []
        for k in raw:
            bars.append(
                RawBar(
                    time=datetime.fromtimestamp(k[0] / 1000, tz=timezone.utc),
                    open=float(k[1]),
                    high=float(k[2]),
                    low=float(k[3]),
                    close=float(k[4]),
                    volume=float(k[5]),
                )
            )
        return bars
