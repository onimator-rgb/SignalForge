<p align="center">
  <h1 align="center">SignalForge</h1>
  <p align="center">
    <strong>Multi-asset market intelligence &amp; paper trading platform</strong><br>
    Crypto &amp; Stocks &bull; Anomaly detection &bull; AI reports &bull; Recommendations &bull; Demo portfolio
  </p>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.12+-blue?logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/FastAPI-0.115+-009688?logo=fastapi&logoColor=white" alt="FastAPI">
  <img src="https://img.shields.io/badge/Vue-3.5-4FC08D?logo=vuedotjs&logoColor=white" alt="Vue 3">
  <img src="https://img.shields.io/badge/PostgreSQL-16+-336791?logo=postgresql&logoColor=white" alt="PostgreSQL">
  <img src="https://img.shields.io/badge/TailwindCSS-4-06B6D4?logo=tailwindcss&logoColor=white" alt="Tailwind">
  <img src="https://img.shields.io/badge/license-MIT-green" alt="License">
</p>

---

## Overview

SignalForge is a full-stack market intelligence platform that monitors **cryptocurrencies and US stocks**, detects anomalies, generates AI-powered reports, produces scored recommendations, and runs a demo paper trading portfolio — all through a modern dashboard.

It combines quantitative technical analysis (RSI, MACD, Bollinger Bands, Z-score anomaly detection) with AI-generated insights (via Claude) to help analysts understand market behavior. The demo portfolio executes paper trades based on recommendation signals, with full performance tracking.

> **Paper trading only** — this is an educational/demo tool. Not investment advice. Past performance does not guarantee future results.

---

## Features

| Module | Description |
|--------|-------------|
| **Multi-asset ingestion** | Automated OHLCV data from Binance (crypto) and Yahoo Finance (stocks) |
| **Technical indicators** | RSI-14, MACD(12,26,9), Bollinger Bands(20,2) computed on-the-fly |
| **Anomaly detection** | Z-score detectors for price spikes, volume surges, RSI extremes |
| **Alert system** | Configurable rules with cooldown, event tracking, mark-as-read |
| **AI reports** | Market summaries, asset briefs, anomaly explanations, watchlist summaries (Claude) |
| **Recommendation engine** | 7-signal composite scoring (v2), candidate_buy / watch_only / neutral / avoid |
| **Demo portfolio** | Paper trading with $1000 capital, rule-based entry/exit, PnL tracking |
| **Performance evaluation** | Forward-return measurement at 24h/72h, accuracy by type/class/score bucket |
| **Watchlists** | User-defined asset groups with intelligence overlays and AI summaries |
| **Live prices** | Binance polling (10s) for crypto, Yahoo polling (60s) for stocks, in-memory cache |
| **Dashboard** | Command center: portfolio, signals, anomalies, watchlists, live prices |
| **Diagnostics** | Sync freshness, market-hours awareness, error monitoring, config view |

---

## Architecture

```
┌─────────────────────┐     ┌──────────────────────────────────────┐     ┌──────────────┐
│   Vue 3 Frontend    │────>│           FastAPI Backend            │────>│  PostgreSQL   │
│   TailwindCSS v4    │     │                                    │     │              │
│   :5173             │     │  Assets | Indicators | Anomalies   │     │  :5432       │
└─────────────────────┘     │  Alerts | Reports | Recommendations│     └──────────────┘
                            │  Portfolio | Watchlists | Live      │
                            │  Scheduler | Diagnostics | Dashboard│
                            └─────────┬──────────┬───────┬───────┘
                                      │          │       │
                           ┌──────────▼──┐  ┌────▼────┐  ┌▼──────────┐
                           │ Binance API │  │ Yahoo   │  │ Claude    │
                           │ (crypto)    │  │ Finance │  │ API       │
                           └─────────────┘  │ (stocks)│  │ (reports) │
                                            └─────────┘  └───────────┘
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | Python 3.12, FastAPI, SQLAlchemy 2.0 (async), Alembic, APScheduler |
| **Frontend** | Vue 3, TypeScript, TailwindCSS v4, Vite, Vue Router, Axios |
| **Database** | PostgreSQL 16 (10 tables, 10 migrations) |
| **Crypto data** | Binance public API (OHLCV + 24hr ticker for live prices) |
| **Stock data** | Yahoo Finance via `yfinance` (delayed ~15min) |
| **AI/LLM** | Anthropic Claude API (4 report types) |
| **Analysis** | pandas, Z-score anomaly detection, 7-signal recommendation scoring |

---

## Quick Start

### Prerequisites

- Python 3.12+, Node.js 18+, PostgreSQL 16+, [uv](https://docs.astral.sh/uv/)

### 1. Clone & configure

```bash
git clone https://github.com/onimator-rgb/SignalForge.git
cd SignalForge
cp .env.example .env
# Edit .env — set ANTHROPIC_API_KEY for AI reports
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

### 5. Load data & verify

```bash
# Crypto ingestion
curl -X POST http://localhost:8000/api/v1/ingestion/trigger \
  -H "Content-Type: application/json" -d '{"asset_class":"crypto","interval":"1h"}'

# Stock ingestion
curl -X POST http://localhost:8000/api/v1/ingestion/trigger \
  -H "Content-Type: application/json" -d '{"asset_class":"stock","interval":"1h"}'

# Smoke test
python scripts/smoke_test.py

# Sanity check (DB-direct)
cd backend && uv run python -m scripts.sanity_check
```

### 6. Open

| URL | Description |
|-----|-------------|
| http://localhost:5173 | Dashboard |
| http://localhost:8000/docs | API docs (Swagger) |

### 7. Enable scheduler (optional)

Set `SCHEDULER_ENABLED=true` in `.env` and restart backend. Crypto ingests every 5 min, stocks every 15 min. Recommendations, anomalies, alerts, and portfolio evaluate automatically after each cycle.

---

## API Reference

### Assets & Market Data
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/assets` | List assets (filter: `asset_class`) |
| `GET` | `/api/v1/assets/{id}` | Asset detail with indicators |
| `GET` | `/api/v1/assets/{id}/ohlcv` | OHLCV candlestick data |
| `GET` | `/api/v1/assets/{id}/indicators` | Technical indicators |
| `GET` | `/api/v1/assets/{id}/recommendation` | Active recommendation |
| `GET` | `/api/v1/assets/search?q=` | Search assets |
| `GET` | `/api/v1/live/prices` | Live/cached prices for all assets |

### Signals & Intelligence
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/anomalies` | Anomaly events |
| `GET` | `/api/v1/anomalies/stats` | Anomaly statistics |
| `GET` | `/api/v1/recommendations/active` | Active recommendations |
| `GET` | `/api/v1/recommendations/performance` | Engine accuracy metrics |
| `GET` | `/api/v1/alerts/rules` | Alert rules |
| `GET` | `/api/v1/alerts/events` | Alert events |

### Portfolio & Reports
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/portfolio` | Demo portfolio summary |
| `POST` | `/api/v1/portfolio/evaluate` | Trigger portfolio evaluation |
| `POST` | `/api/v1/portfolio/positions/{id}/close` | Manual close (paper) |
| `POST` | `/api/v1/reports/generate` | Generate AI report |
| `GET` | `/api/v1/reports` | Report list |

### Watchlists
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/watchlists` | List watchlists |
| `POST` | `/api/v1/watchlists` | Create watchlist |
| `GET` | `/api/v1/watchlists/{id}/assets` | Watchlist assets (enriched) |
| `GET` | `/api/v1/watchlists/{id}/intelligence` | Watchlist intelligence |
| `GET` | `/api/v1/watchlists/{id}/recommendations` | Watchlist recommendations |

### System
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/health` | Health check |
| `GET` | `/api/v1/dashboard/overview` | Aggregate dashboard data |
| `POST` | `/api/v1/ingestion/trigger` | Manual ingestion |
| `GET` | `/api/v1/diagnostics/sync` | Data freshness |
| `GET` | `/api/v1/diagnostics/errors` | Error buffer |

---

## Product Modules

### Recommendation Engine (v2)
7-signal composite scoring: RSI, MACD, Bollinger position, price trend, volume, anomaly context, volatility. Produces `candidate_buy` / `watch_only` / `neutral` / `avoid` with confidence and risk levels. Auto-generates after each ingestion cycle.

### Demo Portfolio
Paper trading with $1000 initial capital. Max 5 positions, 20% per position, -8% stop loss, +15% take profit, 72h max hold. Evaluates automatically. Manual close available.

### Performance Evaluation
Measures forward returns at 24h and 72h for every recommendation. Accuracy breakdown by type, asset class, score bucket, and scoring version (v1 vs v2).

### Watchlist Intelligence
User-defined asset groups with enriched data: live prices, recommendation signals, portfolio overlap, anomaly counts. AI-generated watchlist summaries via Claude.

### Live Prices
Binance 24hr ticker polling every 10s (crypto), Yahoo Finance polling every 60s (stocks, market-hours-aware). In-memory cache with DB fallback. Freshness indicators: live / recent / delayed / stale.

---

## Configuration (.env)

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://...` | PostgreSQL connection |
| `SCHEDULER_ENABLED` | `false` | Auto-ingestion + recommendations |
| `INGESTION_INTERVAL_MINUTES` | `5` | Crypto ingestion frequency |
| `ANOMALY_PRICE_ZSCORE_THRESHOLD` | `2.5` | Price spike sensitivity |
| `ANOMALY_VOLUME_ZSCORE_THRESHOLD` | `3.0` | Volume spike sensitivity |
| `ANTHROPIC_API_KEY` | — | Required for AI reports |
| `LLM_MODEL` | `claude-sonnet-4-20250514` | Claude model |
| `LOG_LEVEL` | `INFO` | Logging verbosity |

---

## Current Limitations

- **No real trading** — paper/demo only
- **No authentication** — single-user, local instance
- **Stocks delayed ~15min** — Yahoo Finance unofficial API
- **Crypto live-ish** — REST polling (10s), not WebSocket
- **No holiday calendar** — simplified US market hours (Mon-Fri)
- **Shared anomaly thresholds** — same Z-score for crypto and stocks
- **No WebSocket to frontend** — REST polling every 15s
- **yfinance unofficial** — may change without notice

---

## Documentation

- [Stabilization Run Guide](docs/STABILIZATION_RUN.md) — operational runbook
- [Debug Checklist](docs/DEBUG_CHECKLIST.md) — troubleshooting

---

## License

MIT License. See [LICENSE](LICENSE).
