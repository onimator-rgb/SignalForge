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


class ADXOut(BaseModel):
    adx: float
    plus_di: float
    minus_di: float


class IndicatorSnapshot(BaseModel):
    asset_id: UUID
    asset_symbol: str
    interval: str
    bar_time: datetime  # timestamp of the bar these indicators are based on
    close: float
    rsi_14: float | None = None
    macd: MACDOut | None = None
    bollinger: BollingerOut | None = None
    adx: ADXOut | None = None
    adx_14: float | None = None
    plus_di: float | None = None
    minus_di: float | None = None
    mfi_14: float | None = None
    stoch_rsi_k: float | None = None
    stoch_rsi_d: float | None = None
    mfi_14: float | None = None
    vwap: float | None = None
    obv: float | None = None
    bars_available: int  # how many bars were used
