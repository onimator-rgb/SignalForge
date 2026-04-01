# Changelog

## [0.2.0] - 2026-04-01

### Added — Autonomous Agent System
- Orchestrator agent — researches project, selects features, generates task specs
- Coder Worker — implements features via Claude CLI (MAX subscription, $0 cost)
- Validator — validates code against task specs, checks tests/mypy/commits
- Auto-discovery — generates new features when roadmap is exhausted
- ProfitTrailer-inspired feature roadmap (35+ features across 5 tiers)
- Session launcher with time limits, tier selection, dry-run mode

### Added — Technical Indicators (10 new)
- ADX (Average Directional Index) — trend strength + direction
- Stochastic RSI (K/D) — enhanced momentum oscillator
- VWAP (Volume-Weighted Average Price) — institutional price level
- OBV (On-Balance Volume) — cumulative volume flow
- MFI (Money Flow Index) — volume-weighted RSI
- CCI (Commodity Channel Index) — mean deviation
- Parabolic SAR — stop and reverse, trend direction
- Keltner Channels — ATR-based volatility envelope
- Squeeze Momentum — Bollinger/Keltner squeeze breakout detector
- Fibonacci Retracement — support/resistance levels
- Pivot Points — classic S/R calculations

### Added — Trading Features
- Trailing Stop Loss — dynamic stop that tracks peak price
- Trailing Take Profit — arms above threshold, trails upward, closes on retracement
- Trailing Buy — waits for local bottom after buy signal
- Slippage Simulation — configurable buy/sell slippage for realistic P&L
- Consecutive Stop Loss Protection — pauses buying after N consecutive losses
- Loss-Aware Buy Cooldown — 48h after loss, 12h after profit
- Auto Strategy Profile Switch — recommends profile based on market regime
- Portfolio Risk Metrics endpoint

### Added — Frontend
- ADX, StochRSI, VWAP indicators in Asset Detail view
- Strategy profile params bar in Dashboard (SL, TP, Trail, Slippage)
- Auto-switch and effective threshold badges in Dashboard
- Trailing TP armed + Trailing Buy badges in Portfolio
- Squeeze Momentum display in Anomalies view
- Ingestion Status view (new page)
- Entry Decisions log in Portfolio
- Indicator History endpoint for sparkline data

### Changed
- LLM reports now use local templates by default ($0 cost, no API key needed)
- Recommendation scoring upgraded to 9-signal composite (added ADX + StochRSI)
- Default LLM_PROVIDER changed from `claude` to `local`
- Scheduler uses native asyncio tasks instead of APScheduler

### Fixed
- Merge conflict resolutions across 30+ agent-generated branches
- Calculator __init__.py exports for all new indicators
- IndicatorHistory schema and service function
- Trailing profit test thresholds aligned with profile values

---

## [0.1.0] - 2026-03-30

### Added — Core Platform
- Multi-asset monitoring: 25 crypto (Binance) + 15 US stocks (Yahoo Finance)
- Technical indicators: RSI-14, MACD(12,26,9), Bollinger Bands(20,2)
- Anomaly detection: price spikes, volume surges, RSI extremes (Z-score)
- Alert system with configurable rules and cooldown
- AI reports via Claude API (market summary, asset brief, anomaly explanation, watchlist)
- Recommendation engine v2: 7-signal composite scoring
- Demo portfolio: $1000 capital, rule-based entry/exit, PnL tracking
- Performance evaluation: 24h/72h forward returns, accuracy metrics
- Watchlists with intelligence overlays
- Live prices: Binance polling + Yahoo polling + SSE broadcast
- Dashboard: portfolio, signals, anomalies, watchlists, live prices
- Diagnostics: sync freshness, error monitoring, runtime health
- Runtime resilience: heartbeat, watchdog, recovery endpoints
- Strategy profiles: balanced/aggressive/conservative
- Market regime detection: bullish/bearish/neutral
- Docker Compose deployment stack
- 15 initial tests
