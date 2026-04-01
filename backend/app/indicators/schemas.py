"""Pydantic schemas for indicator endpoints."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class MACDOut(BaseModel):
    macd: float
    signal: float
    histogram: float


class BollingerOut(BaseModel):
    upper: float
    middle: float
    lower: float
    width: float


class FibonacciOut(BaseModel):
    swing_high: float
    swing_low: float
    level_0: float
    level_236: float
    level_382: float
    level_500: float
    level_618: float
    level_786: float
    level_100: float
    trend: str


class IndicatorSnapshot(BaseModel):
    asset_id: UUID
    asset_symbol: str
    interval: str
    bar_time: datetime  # timestamp of the bar these indicators are based on
    close: float
    rsi_14: float | None = None
    macd: MACDOut | None = None
    bollinger: BollingerOut | None = None
    adx_14: float | None = None
    plus_di: float | None = None
    minus_di: float | None = None
    stoch_rsi_k: float | None = None
    stoch_rsi_d: float | None = None
    mfi_14: float | None = None
    vwap: float | None = None
    fibonacci: FibonacciOut | None = None
    bars_available: int  # how many bars were used
