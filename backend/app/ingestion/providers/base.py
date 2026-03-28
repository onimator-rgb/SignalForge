"""Abstract base for market data providers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class RawBar:
    """Normalized OHLCV bar from any provider."""

    time: datetime  # UTC, bar open time
    open: float
    high: float
    low: float
    close: float
    volume: float


class BaseProvider(ABC):
    """Interface that every market data provider must implement."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider identifier, e.g. 'binance'."""

    @abstractmethod
    async def fetch_ohlcv(
        self,
        symbol: str,
        interval: str,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 1000,
    ) -> list[RawBar]:
        """Fetch OHLCV bars for a single symbol.

        Args:
            symbol: Provider-native symbol (e.g. 'BTCUSDT' for Binance).
            interval: Candle interval (e.g. '1h', '5m', '1d').
            start_time: Inclusive start (UTC). None = provider decides.
            end_time: Inclusive end (UTC). None = now.
            limit: Max number of bars to return.

        Returns:
            List of RawBar sorted by time ascending.
        """
