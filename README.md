<p align="center">
  <h1 align="center">SignalForge</h1>
  <p align="center">
    <strong>Multi-asset market intelligence platform</strong><br>
    Crypto &amp; Stocks &bull; Anomaly detection &bull; Technical indicators &bull; AI-powered insights
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

SignalForge monitors **cryptocurrencies and US stocks** in near real-time, computes technical indicators, detects market anomalies using statistical models, and delivers actionable intelligence through a modern dashboard. It combines quantitative analysis with AI-generated explanations to help traders and analysts understand market behavior.

### Current Feature Set

- **Multi-asset support** — Crypto (via Binance) and US stocks (via Yahoo Finance) in a single system
- **Live market data ingestion** — Automated OHLCV fetching with configurable intervals and backfill
- **Technical indicators** — RSI-14, MACD(12,26,9), Bollinger Bands(20,2) computed on-the-fly
- **Anomaly detection** — Z-score detectors for price spikes, volume surges, and RSI extremes with severity scoring
- **Alert system** — Configurable rules (price thresholds, anomaly triggers) with cooldown and event tracking
- **AI-powered reports** — Market summaries, asset briefs, and anomaly explanations via Claude API
- **Alerts-reports integration** — Generate contextual AI reports directly from alert events
- **Real-time dashboard** — Vue 3 SPA with asset class filtering, auto-refresh, and detailed views
- **Diagnostics** — Sync freshness tracking, market-hours-aware staleness for stocks, error monitoring

---

## Architecture

```
┌─────────────────────┐     ┌─────────────────────────────────┐     ┌──────────────┐
│   Vue 3 Frontend    │────>│         FastAPI Backend          │────>│  PostgreSQL   │
│   TailwindCSS v4    │     │                                 │     │              │
│   :5173             │     │  Assets | Indicators | Anomalies│     │  :5432       │
└─────────────────────┘     │  Reports | Alerts | Ingestion   │     └──────────────┘
                            │  LLM | Scheduler | Diagnostics  │
                            └──────────┬──────────┬───────────┘
                                       │          │
                            ┌──────────▼──┐  ┌────▼──────┐
                            │ Binance API │  │ Yahoo     │
                            │ (crypto)    │  │ Finance   │
                            └─────────────┘  │ (stocks)  │
                                             └───────────┘
                                       │
                              ┌────────▼──────┐
                              │  Claude API   │
                              │  (AI reports) │
                              └───────────────┘
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | Python 3.12, FastAPI, SQLAlchemy 2.0 (async), Alembic, APScheduler |
| **Frontend** | Vue 3, TypeScript, TailwindCSS v4, Vite, Vue Router, Axios |
| **Database** | PostgreSQL 16 |
| **Crypto Data** | Binance public API (OHLCV, no auth required) |
| **Stock Data** | Yahoo Finance via `yfinance` (delayed ~15min) |
| **AI/LLM** | Anthropic Claude API |
| **Analysis** | pandas, Z-score anomaly detection, RSI, MACD, Bollinger Bands |

---

## Project Structure

```
signalforge/
├── backend/
│   ├── app/
│   │   ├── alerts/          # Alert rules, triggers, evaluation
│   │   ├── anomalies/       # Detection engine & detectors
│   │   │   └── detectors/   #   price_spike, volume_spike, rsi_extreme
│   │   ├── assets/          # Asset registry (crypto + stocks)
│   │   ├── core/            # Middleware, exceptions, error buffer
│   │   ├── indicators/      # Technical indicator calculators
│   │   │   └── calculators/ #   RSI, MACD, Bollinger Bands
│   │   ├── ingestion/       # Data pipeline & providers
│   │   │   └── providers/   #   Binance (crypto), Yahoo Finance (stocks)
│   │   ├── llm/             # AI report generation
│   │   │   ├── prompts/     #   multi-asset-aware prompt templates
│   │   │   └── providers/   #   Claude integration
│   │   ├── market_data/     # OHLCV storage & serving
│   │   ├── reports/         # Report generation & history
│   │   └── system/          # Health checks & diagnostics
│   ├── alembic/             # Database migrations
│   └── tests/
├── frontend/
│   └── src/
│       ├── views/           # Dashboard, Assets, Anomalies, Reports, Alerts
│       ├── components/      # Layout, SearchBar, badges, loaders
│       ├── api/             # Typed API client (Axios)
│       ├── types/           # TypeScript interfaces
│       └── utils/           # Formatters, markdown helpers
├── scripts/                 # Seed, smoke test, sanity check
├── docs/                    # Debug checklist, stabilization guide
└── infra/                   # Docker Compose (optional)
```

---

## Quick Start

### Prerequisites

- Python 3.12+
- Node.js 18+
- PostgreSQL 16+
- [uv](https://docs.astral.sh/uv/) (Python package manager)

### 1. Clone & configure

```bash
git clone https://github.com/onimator-rgb/SignalForge.git
cd SignalForge
cp .env.example .env
# Edit .env — set ANTHROPIC_API_KEY for AI reports
```

### 2. Database setup

```sql
-- Run as PostgreSQL superuser:
CREATE USER marketpulse WITH PASSWORD 'marketpulse';
CREATE DATABASE marketpulse OWNER marketpulse;
```

### 3. Backend

```bash
cd backend
uv sync                                            # Install dependencies
uv run alembic upgrade head                        # Run migrations
uv run python -m scripts.seed_assets               # Seed top 25 crypto assets
uv run python -m scripts.seed_stocks               # Seed 15 US blue chip stocks
uv run uvicorn app.main:app --reload --port 8000   # Start API server
```

### 4. Frontend

```bash
cd frontend
npm install        # Install dependencies
npm run dev        # Start dev server on :5173
```

### 5. Load market data

```bash
# Trigger crypto ingestion:
curl -X POST http://localhost:8000/api/v1/ingestion/trigger \
  -H "Content-Type: application/json" \
  -d '{"asset_class": "crypto", "interval": "1h"}'

# Trigger stock ingestion:
curl -X POST http://localhost:8000/api/v1/ingestion/trigger \
  -H "Content-Type: application/json" \
  -d '{"asset_class": "stock", "interval": "1h"}'
```

### 6. Verify

| Service       | URL                                      |
|---------------|------------------------------------------|
| Dashboard     | http://localhost:5173                     |
| API Docs      | http://localhost:8000/docs                |
| Health Check  | http://localhost:8000/api/v1/health       |
| Smoke Test    | `python scripts/smoke_test.py`           |
| Sanity Check  | `cd backend && uv run python -m scripts.sanity_check` |

---

## Useful Commands

### Smoke test (requires running backend)

```bash
python scripts/smoke_test.py
```

22 checks covering: health, crypto assets, stock assets, OHLCV, indicators, anomalies, alerts, reports, diagnostics.

### Sanity check (direct DB, no backend needed)

```bash
cd backend && uv run python -m scripts.sanity_check
```

Shows: assets per class, price bars, anomalies, alerts, reports, recent ingestion jobs, sync errors.

### Ingestion triggers

```bash
# Crypto
curl -X POST http://localhost:8000/api/v1/ingestion/trigger \
  -H "Content-Type: application/json" -d '{"asset_class": "crypto", "interval": "1h"}'

# Stocks
curl -X POST http://localhost:8000/api/v1/ingestion/trigger \
  -H "Content-Type: application/json" -d '{"asset_class": "stock", "interval": "1h"}'
```

### Enable automatic scheduler

Set `SCHEDULER_ENABLED=true` in `.env` and restart backend. Crypto ingests every 5 min, stocks every 15 min.

---

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/health` | System health |
| `GET` | `/api/v1/assets` | Asset list (filterable by `asset_class`) |
| `GET` | `/api/v1/assets/{id}` | Asset detail with indicators |
| `GET` | `/api/v1/assets/search?q=` | Search assets |
| `GET` | `/api/v1/assets/{id}/ohlcv` | OHLCV candlestick data |
| `GET` | `/api/v1/assets/{id}/indicators` | Technical indicators |
| `GET` | `/api/v1/anomalies` | Anomaly events (filterable) |
| `GET` | `/api/v1/anomalies/stats` | Anomaly statistics |
| `POST` | `/api/v1/ingestion/trigger` | Trigger data ingestion |
| `GET` | `/api/v1/ingestion/status` | Ingestion pipeline status |
| `POST` | `/api/v1/reports/generate` | Generate AI report |
| `GET` | `/api/v1/reports` | Report list |
| `GET` | `/api/v1/alerts/rules` | Alert rules |
| `GET` | `/api/v1/alerts/events` | Alert events |
| `GET` | `/api/v1/alerts/stats` | Alert statistics |
| `GET` | `/api/v1/diagnostics/sync` | Per-asset data freshness |
| `GET` | `/api/v1/diagnostics/config` | Current settings |
| `GET` | `/api/v1/diagnostics/errors` | Recent error buffer |

Full interactive documentation at `/docs` (Swagger UI).

---

## Configuration (.env)

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://...` | PostgreSQL connection |
| `BINANCE_BASE_URL` | `https://api.binance.com` | Binance API |
| `SCHEDULER_ENABLED` | `false` | Auto-ingestion scheduler |
| `INGESTION_INTERVAL_MINUTES` | `5` | Crypto ingestion frequency |
| `ANOMALY_PRICE_ZSCORE_THRESHOLD` | `2.5` | Price spike sensitivity |
| `ANOMALY_VOLUME_ZSCORE_THRESHOLD` | `3.0` | Volume spike sensitivity |
| `ANOMALY_RSI_UPPER` / `_LOWER` | `80` / `20` | RSI thresholds |
| `LLM_PROVIDER` | `claude` | AI provider |
| `ANTHROPIC_API_KEY` | — | Required for AI reports |
| `LLM_MODEL` | `claude-sonnet-4-20250514` | Claude model |
| `LOG_LEVEL` | `INFO` | Logging verbosity |

---

## Multi-Asset Support

SignalForge supports two asset classes:

| | Crypto | Stocks |
|---|---|---|
| **Provider** | Binance (public, no auth) | Yahoo Finance (delayed ~15min) |
| **Market hours** | 24/7 | Mon-Fri 9:30-16:00 ET |
| **Intervals** | 1h | 1h |
| **Freshness** | Stale after 2h no data | Market-hours-aware |
| **Anomaly detection** | Same Z-score engine | Same Z-score engine |
| **AI reports** | Context-aware prompts | Context-aware prompts |

Assets are distinguished by `asset_class` field (`crypto` or `stock`). The frontend allows filtering by class.

---

## Current Limitations

- **No live/streaming prices** — batch ingestion only (delayed data)
- **No authentication** — single-user, local-only
- **Yahoo Finance is unofficial** — may rate-limit or change without notice
- **Market hours simplified** — US market Mon-Fri, no holiday calendar
- **Anomaly thresholds shared** — same Z-score thresholds for crypto and stocks
- **No 1d auto-ingestion for stocks** — scheduler handles 1h only (manual trigger for 1d)
- **No WebSocket** — frontend polls via REST

---

## Documentation

- [Stabilization Run Guide](docs/STABILIZATION_RUN.md) — operational checklist for running the system
- [Debug Checklist](docs/DEBUG_CHECKLIST.md) — troubleshooting common issues

---

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
