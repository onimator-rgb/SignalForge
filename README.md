<p align="center">
  <h1 align="center">SignalForge</h1>
  <p align="center">
    <strong>AI-powered market intelligence &amp; autonomous trading arena</strong><br>
    9 AI Traders &bull; Multi-Model LLM &bull; 15+ Indicators &bull; News Intelligence &bull; Paper Trading Competition
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

SignalForge is a full-stack market intelligence platform with an **AI Trader Arena** — 9 autonomous AI traders, each powered by a different LLM model and trading strategy, competing in real-time paper trading on crypto and US stocks.

The platform monitors **30+ assets** (16 crypto + 14 stocks), runs 15+ technical indicators, detects anomalies, aggregates verified news from 3 sources, and lets AI traders make autonomous buy/sell decisions. A leaderboard tracks which AI model + strategy combination performs best.

Built with a **multi-provider LLM router** that routes to the cheapest available model (Gemini, Groq, Cerebras, SambaNova, Mistral, OpenRouter) — 4 of 9 traders run on **completely free models** ($0 cost).

> **Paper trading only** — educational/research tool. Not investment advice.

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

### AI Trader Arena

9 autonomous AI traders compete in real-time paper trading, each with a unique strategy, risk profile, and LLM model:

| Trader | Strategy | LLM Model | Cost |
|--------|----------|-----------|------|
| **Conservative Quant** | Risk-averse, 3+ signal confirmation, tight stops | Gemini 2.5 Flash | cheap |
| **Momentum Hunter** | Trend-following, breakout-hunting, large positions | Groq Llama 3.3 | cheap |
| **Mean Reversion** | Buys oversold dips, sells overbought rallies | Mistral Small | cheap |
| **Sentiment Contrarian** | Trades against crowd emotions, anomaly-driven | Gemini 2.5 Flash Lite | ultra-cheap |
| **Balanced Hybrid** | Adapts to market regime (momentum/reversion/defensive) | Gemini 2.5 Flash | cheap |
| **Scalper Quant** | Quick in/out, 3-5% gains, high turnover | OpenRouter Nemotron 120B | **FREE** |
| **Whale Follower** | Follows smart money via volume spike analysis | OpenRouter Gemma 12B | **FREE** |
| **Fibonacci Trader** | Trades Fibonacci support/resistance levels | OpenRouter Llama 3.3 | **FREE** |
| **News Sentiment** | Trades exclusively on cross-verified news signals | Cerebras Llama 3.1 | **FREE** |

**Cost optimization:**
- Pre-filter system eliminates 50-80% unnecessary LLM calls
- Rule-based Exit Manager handles stop-loss/take-profit without LLM
- Estimated cost: **~$0.50-2.00/month** for all 9 traders

### News Intelligence (Anti-Fake-News)

| Source | Type | Free Tier |
|--------|------|-----------|
| **Finnhub** | Stocks + Crypto + AI Sentiment | 60 req/min |
| **MarketAux** | 80+ global markets, 5000+ sources | 100 req/day |
| **Alpha Vantage** | AI-powered sentiment analysis | 25 req/day |

Pipeline: Fetch parallel → Deduplicate → Cross-source verify (2+ sources = verified) → Reliability scoring → Trusted domain boost → Rank

### Multi-Provider LLM Router

Intelligent routing to cheapest available model with automatic fallback:

```
TRIVIAL  → Cerebras FREE → Groq → Gemini Lite
SIMPLE   → Cerebras FREE → Groq → SambaNova FREE → Gemini
MODERATE → Gemini → Cerebras → Groq → Mistral
COMPLEX  → Gemini → Mistral → Claude Haiku
CRITICAL → Claude Haiku → Gemini → Claude Sonnet
```

Supports 8 providers: Gemini, Groq, Cerebras, SambaNova, OpenRouter, Mistral, Anthropic, Ollama (local).

### Autonomous Dev Agent System

| Agent | Role |
|-------|------|
| **Orchestrator** | Tech lead — researches project, selects features, generates task specs |
| **Coder Worker** | Implements features via Claude CLI (MAX subscription), runs tests, commits |
| **Validator** | Validates code against task specs, checks tests/mypy/commit format |

The dev agents use **Claude MAX subscription** via CLI — **$0 API cost**.

---

## Architecture

```
┌─────────────────────┐     ┌──────────────────────────────────────┐     ┌──────────────┐
│   Vue 3 Frontend    │────>│           FastAPI Backend            │────>│  PostgreSQL   │
│   TailwindCSS v4    │     │                                      │     │              │
│   :5173             │     │  Assets | Indicators | Anomalies     │     │  :5432       │
└─────────────────────┘     │  Alerts | Reports | Recommendations  │     └──────────────┘
                            │  Portfolio | Watchlists | Live        │
                            │  Strategy | AI Arena | News           │
                            └────┬──────────┬───────┬──────┬───────┘
                                 │          │       │      │
                     ┌───────────▼──┐  ┌────▼────┐  │  ┌───▼──────────────┐
                     │ Binance API  │  │ Yahoo   │  │  │  News Sources    │
                     │ (crypto)     │  │ Finance │  │  │  Finnhub|MktAux  │
                     └──────────────┘  └─────────┘  │  └──────────────────┘
                            ┌───────────────────────▼───────────────────┐
                            │       Multi-Provider LLM Router           │
                            │  Gemini | Groq | Cerebras | SambaNova    │
                            │  Mistral | OpenRouter | Claude | Ollama  │
                            └───────────────────────┬───────────────────┘
                            ┌───────────────────────▼───────────────────┐
                            │         AI Trader Arena (9 traders)        │
                            │  Pre-filter → LLM Decision → Execute      │
                            │  Leaderboard → Performance Comparison     │
                            └───────────────────────────────────────────┘
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
| **AI/LLM** | Multi-provider router: Gemini, Groq, Cerebras, SambaNova, Mistral, OpenRouter, Claude, Ollama |
| **AI Traders** | 9 autonomous trading agents with unique strategies and LLM models |
| **News** | Finnhub (60 req/min), MarketAux, Alpha Vantage — anti-fake-news pipeline |
| **Analysis** | pandas, 15+ indicators, Z-score anomaly detection, 11-signal scoring |
| **Dev Agents** | Orchestrator/Coder/Validator using Claude CLI (MAX subscription) |
| **Testing** | pytest + pytest-asyncio (313+ tests) |

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
