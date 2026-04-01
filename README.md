<p align="center">
  <h1 align="center">SignalForge</h1>
  <p align="center">
    <strong>Multi-asset market intelligence &amp; paper trading platform</strong><br>
    Crypto &amp; Stocks &bull; 15+ Indicators &bull; Anomaly Detection &bull; AI Reports &bull; Autonomous Agent System
  </p>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.12+-blue?logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/FastAPI-0.115+-009688?logo=fastapi&logoColor=white" alt="FastAPI">
  <img src="https://img.shields.io/badge/Vue-3.5-4FC08D?logo=vuedotjs&logoColor=white" alt="Vue 3">
  <img src="https://img.shields.io/badge/PostgreSQL-16+-336791?logo=postgresql&logoColor=white" alt="PostgreSQL">
  <img src="https://img.shields.io/badge/TailwindCSS-4-06B6D4?logo=tailwindcss&logoColor=white" alt="Tailwind">
  <img src="https://img.shields.io/badge/tests-213_passing-brightgreen" alt="Tests">
  <img src="https://img.shields.io/badge/license-MIT-green" alt="License">
</p>

---

## Overview

SignalForge is a full-stack market intelligence platform that monitors **cryptocurrencies and US stocks**, detects anomalies, generates AI-powered reports, produces scored recommendations, and runs a demo paper trading portfolio with advanced trailing mechanisms — all through a modern dashboard.

It combines 15+ quantitative technical indicators with Z-score anomaly detection and AI-generated insights to help analysts understand market behavior. The autonomous agent system (Orchestrator + Coder + Validator) continuously extends the platform using Claude MAX subscription at zero API cost.

> **Paper trading only** — this is an educational/demo tool. Not investment advice.

---

## Features

### Core Platform

| Module | Description |
|--------|-------------|
| **Multi-asset ingestion** | Automated OHLCV data from Binance (crypto) and Yahoo Finance (stocks) |
| **15+ Technical indicators** | RSI, MACD, Bollinger, ADX, StochRSI, VWAP, OBV, MFI, CCI, Parabolic SAR, Keltner, Squeeze Momentum, Fibonacci, Pivot Points |
| **Anomaly detection** | Z-score detectors: price spikes, volume surges, RSI extremes, squeeze momentum breakouts |
| **Alert system** | Configurable rules with cooldown, event tracking, mark-as-read |
| **AI reports** | Market summaries, asset briefs, anomaly explanations, watchlist summaries (local templates or Claude) |
| **Recommendation engine** | 9-signal composite scoring (v2) with ADX and StochRSI integration |
| **Demo portfolio** | Paper trading with trailing stop loss, trailing take profit, trailing buy, slippage simulation |
| **Risk management** | Consecutive SL protection, loss-aware buy cooldown, asset class exposure cap |
| **Strategy profiles** | Balanced / Aggressive / Conservative with auto-switch based on market regime |
| **Performance evaluation** | Forward-return measurement at 24h/72h, accuracy by type/class/score |
| **Watchlists** | User-defined asset groups with intelligence overlays and AI summaries |
| **Live prices** | Binance WebSocket (crypto), Yahoo polling (stocks), SSE broadcast |
| **Dashboard** | Command center with strategy params, regime indicator, live positions |

### Autonomous Agent System

| Agent | Role |
|-------|------|
| **Orchestrator** | Tech lead brain — researches project, selects features from roadmap, generates task specs, manages Coder/Validator loop |
| **Coder Worker** | Implements features via Claude CLI (MAX subscription), runs tests, commits |
| **Validator** | Validates code against task specs, checks tests/mypy/commit format |

The agents use **Claude MAX subscription** via CLI — **$0 API cost**. They've autonomously implemented 25+ features including indicators, trailing mechanisms, frontend views, and risk management.

---

## Architecture

```
┌─────────────────────┐     ┌──────────────────────────────────────┐     ┌──────────────┐
│   Vue 3 Frontend    │────>│           FastAPI Backend            │────>│  PostgreSQL   │
│   TailwindCSS v4    │     │                                      │     │              │
│   :5173             │     │  Assets | Indicators | Anomalies     │     │  :5432       │
└─────────────────────┘     │  Alerts | Reports | Recommendations  │     └──────────────┘
                            │  Portfolio | Watchlists | Live        │
                            │  Strategy | Diagnostics | Dashboard   │
                            └─────────┬──────────┬───────┬─────────┘
                                      │          │       │
                           ┌──────────▼──┐  ┌────▼────┐  ┌▼──────────┐
                           │ Binance API │  │ Yahoo   │  │ Local LLM │
                           │ (crypto)    │  │ Finance │  │ Templates │
                           └─────────────┘  │ (stocks)│  └───────────┘
                                            └─────────┘

┌──────────────────────────────────────────────────────────────┐
│              Autonomous Agent System                          │
│  Orchestrator → Coder Worker → Validator → Orchestrator ...  │
│  (Claude MAX CLI, $0 cost, auto-discovers new features)      │
└──────────────────────────────────────────────────────────────┘
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | Python 3.12, FastAPI, SQLAlchemy 2.0 (async), Alembic, asyncio scheduler |
| **Frontend** | Vue 3, TypeScript, TailwindCSS v4, Vite, Vue Router, Axios |
| **Database** | PostgreSQL 16 |
| **Crypto data** | Binance public API (OHLCV + WebSocket live stream) |
| **Stock data** | Yahoo Finance via `yfinance` (delayed ~15min) |
| **AI/LLM** | Local template engine (default) or Anthropic Claude API (optional) |
| **Analysis** | pandas, 15+ indicators, Z-score anomaly detection, 9-signal scoring |
| **Agents** | Custom Orchestrator/Coder/Validator using Claude CLI (MAX subscription) |
| **Testing** | pytest + pytest-asyncio (213 tests) |

---

## Technical Indicators

| Indicator | Type | Used In |
|-----------|------|---------|
| RSI (14) | Momentum | Scoring, Anomaly Detection |
| MACD (12,26,9) | Trend | Scoring |
| Bollinger Bands (20,2) | Volatility | Scoring, Anomaly Detection |
| ADX (14) | Trend Strength | Scoring, Regime Detection |
| Stochastic RSI | Momentum | Scoring |
| VWAP | Price Level | Analysis |
| OBV | Volume Flow | Analysis |
| MFI (14) | Volume-Weighted Momentum | Analysis |
| CCI | Mean Deviation | Analysis |
| Parabolic SAR | Trend Direction | Stop Loss |
| Keltner Channels | Volatility | Squeeze Detection |
| Squeeze Momentum | Breakout Prediction | Anomaly Detection |
| Fibonacci Retracement | Support/Resistance | Analysis |
| Pivot Points | Support/Resistance | Analysis |

---

## Trading Features (Paper)

| Feature | Description |
|---------|-------------|
| **Trailing Stop Loss** | Dynamic stop that moves up with price, triggers on % drop from peak |
| **Trailing Take Profit** | Arms above threshold, trails peak, closes on retracement |
| **Trailing Buy** | Waits for local bottom after buy signal before entering |
| **Slippage Simulation** | Configurable buy/sell slippage for realistic P&L |
| **Consecutive SL Protection** | Pauses buying after N consecutive stop losses |
| **Loss-Aware Cooldown** | Longer cooldown (48h) after losing trades, shorter (12h) after wins |
| **Auto Strategy Switch** | Recommends profile based on market regime (bullish/bearish/neutral) |
| **Portfolio Risk Metrics** | Equity, exposure, concentration analysis |

---

## Quick Start

### Prerequisites

- Python 3.12+, Node.js 18+, PostgreSQL 16+, [uv](https://docs.astral.sh/uv/)

### 1. Clone & configure

```bash
git clone https://github.com/onimator-rgb/SignalForge.git
cd SignalForge
cp .env.example .env
# Edit .env if needed (defaults work for local development)
```

### 2. Database

```sql
CREATE USER marketpulse WITH PASSWORD 'marketpulse';
CREATE DATABASE marketpulse OWNER marketpulse;
```

### 3. Backend

```bash
cd backend
uv sync
uv run alembic upgrade head
uv run python -m scripts.seed_assets    # 25 crypto assets
uv run python -m scripts.seed_stocks    # 15 US stocks
uv run uvicorn app.main:app --reload --port 8000
```

### 4. Frontend

```bash
cd frontend
npm install
npm run dev
```

### 5. Open

| URL | Description |
|-----|-------------|
| http://localhost:5173 | Dashboard |
| http://localhost:8000/docs | API docs (Swagger) |

### 6. Enable scheduler (optional)

Set `SCHEDULER_ENABLED=true` in `.env` and restart backend. Crypto ingests every 5 min, stocks every 15 min. All pipelines (anomalies, recommendations, portfolio) evaluate automatically.

---

## Agent System

The autonomous agent system implements features without manual coding:

```bash
# Run agents for 2 hours (all tiers)
python scripts/run_agents_session.py --max-minutes 120

# Only backend features
python scripts/run_agents_session.py --tier 5 --max-minutes 60

# Only frontend features
python scripts/run_agents_session.py --tier 4 --max-minutes 60

# 24h production audit (requires backend running)
python scripts/run_24h_audit.py
```

The Orchestrator picks features from a ProfitTrailer-inspired roadmap, generates task specs, and dispatches to Coder + Validator. When the roadmap runs out, it auto-discovers new features.

---

## Configuration (.env)

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://...` | PostgreSQL connection |
| `SCHEDULER_ENABLED` | `false` | Auto-ingestion + pipelines |
| `INGESTION_INTERVAL_MINUTES` | `5` | Crypto ingestion frequency |
| `ANOMALY_PRICE_ZSCORE_THRESHOLD` | `2.5` | Price spike sensitivity |
| `ANOMALY_VOLUME_ZSCORE_THRESHOLD` | `3.0` | Volume spike sensitivity |
| `LLM_PROVIDER` | `local` | `local` (free templates) or `claude` (API) |
| `STRATEGY_PROFILE` | `balanced` | `balanced` / `aggressive` / `conservative` |
| `LOG_LEVEL` | `INFO` | Logging verbosity |

---

## Current Limitations

- **No real trading** — paper/demo only
- **No authentication** — single-user, local instance
- **Stocks delayed ~15min** — Yahoo Finance unofficial API
- **No holiday calendar** — simplified US market hours (Mon-Fri)
- **yfinance unofficial** — may change without notice

---

## Documentation

- [Stabilization Run Guide](docs/STABILIZATION_RUN.md) — operational runbook
- [Debug Checklist](docs/DEBUG_CHECKLIST.md) — troubleshooting
- [Orchestrator README](marketpulse-orchestrator/README.md) — agent system docs

---

## License

MIT License. See [LICENSE](LICENSE).
