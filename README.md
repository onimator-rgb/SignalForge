<p align="center">
  <h1 align="center">SignalForge</h1>
  <p align="center">
    <strong>Real-time crypto market intelligence platform</strong><br>
    Anomaly detection &bull; Technical indicators &bull; AI-powered insights
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

SignalForge monitors the top 25 cryptocurrencies in real time, computes technical indicators, detects market anomalies using statistical models, and delivers actionable intelligence through a modern dashboard. It combines quantitative analysis with AI-generated explanations to help traders and analysts make informed decisions.

### Key Features

- **Live Market Data** — Automated OHLCV ingestion from Binance with configurable intervals
- **Anomaly Detection Engine** — Z-score based detectors for price spikes, volume surges, and RSI extremes with severity scoring (low / medium / high / critical)
- **Technical Indicators** — RSI-14, MACD(12,26,9), Bollinger Bands(20,2) computed on-the-fly
- **AI-Powered Reports** — Market summaries, anomaly explanations, and asset briefs generated via Claude API
- **Alert System** — Configurable alerts with threshold-based triggers
- **Real-time Dashboard** — Vue 3 SPA with auto-refresh, top movers, anomaly feed, and detailed asset views
- **Full REST API** — Interactive Swagger docs, request tracing, structured logging

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
                              ┌────────▼──┐  ┌────▼──────┐
                              │ Binance   │  │ Claude    │
                              │ API       │  │ API       │
                              │ (OHLCV)   │  │ (Reports) │
                              └───────────┘  └───────────┘
```

---

## Project Structure

```
signalforge/
├── backend/
│   ├── app/
│   │   ├── alerts/          # Alert rules, triggers, CRUD
│   │   ├── anomalies/       # Detection engine & detectors
│   │   │   └── detectors/   #   price_spike, volume_spike, rsi_extreme
│   │   ├── assets/          # Asset registry, search, detail
│   │   ├── core/            # Middleware, exceptions, error buffer
│   │   ├── indicators/      # Technical indicator calculators
│   │   │   └── calculators/ #   RSI, MACD, Bollinger Bands
│   │   ├── ingestion/       # Data pipeline & Binance provider
│   │   ├── llm/             # AI report generation
│   │   │   ├── prompts/     #   anomaly_explanation, market_summary, asset_brief
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
├── scripts/                 # Seed data, smoke tests, prerequisites check
├── docs/                    # Debug checklist, documentation
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
# Edit .env with your database credentials
```

### 2. Database setup

```sql
-- Run as PostgreSQL superuser:
CREATE USER signalforge WITH PASSWORD 'your_password';
CREATE DATABASE signalforge OWNER signalforge;
```

### 3. Backend

```bash
cd backend
uv sync                                            # Install dependencies
uv run alembic upgrade head                        # Run migrations
uv run python -m scripts.seed_assets               # Seed top 25 crypto assets
uv run uvicorn app.main:app --reload --port 8000   # Start API server
```

### 4. Frontend

```bash
cd frontend
npm install        # Install dependencies
npm run dev        # Start dev server on :5173
```

### 5. Verify

| Service       | URL                                      |
|---------------|------------------------------------------|
| Dashboard     | http://localhost:5173                     |
| API Docs      | http://localhost:8000/docs                |
| Health Check  | http://localhost:8000/api/v1/health       |

### 6. Load market data

```bash
# Trigger initial data ingestion:
curl -X POST http://localhost:8000/api/v1/ingestion/trigger \
  -H "Content-Type: application/json" \
  -d '{"interval": "1h"}'

# Or enable automatic ingestion in .env:
# SCHEDULER_ENABLED=true
```

---

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/health` | System health status |
| `GET` | `/api/v1/assets` | List assets with current prices |
| `GET` | `/api/v1/assets/{id}` | Asset detail with indicators |
| `GET` | `/api/v1/assets/search?q=` | Search assets |
| `GET` | `/api/v1/assets/{id}/ohlcv` | OHLCV candlestick data |
| `GET` | `/api/v1/assets/{id}/indicators` | Technical indicators |
| `GET` | `/api/v1/anomalies` | Anomaly events (filterable) |
| `GET` | `/api/v1/anomalies/stats` | Anomaly statistics |
| `POST` | `/api/v1/ingestion/trigger` | Trigger data ingestion |
| `GET` | `/api/v1/ingestion/status` | Ingestion pipeline status |
| `GET` | `/api/v1/reports` | AI-generated reports |
| `GET` | `/api/v1/alerts` | Alert rules & history |
| `GET` | `/api/v1/diagnostics/sync` | Per-asset data freshness |
| `GET` | `/api/v1/diagnostics/errors` | Recent error buffer |

Full interactive documentation available at `/docs` (Swagger UI) and `/redoc`.

---

## Configuration

All configuration is done via environment variables (`.env` file):

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://...` | PostgreSQL connection string |
| `BINANCE_BASE_URL` | `https://api.binance.com` | Binance API base URL |
| `SCHEDULER_ENABLED` | `false` | Enable automatic data ingestion |
| `INGESTION_INTERVAL_MINUTES` | `5` | Ingestion frequency (minutes) |
| `ANOMALY_PRICE_ZSCORE_THRESHOLD` | `2.5` | Price spike detection sensitivity |
| `ANOMALY_VOLUME_ZSCORE_THRESHOLD` | `3.0` | Volume spike detection sensitivity |
| `ANOMALY_RSI_UPPER` | `80` | RSI overbought threshold |
| `ANOMALY_RSI_LOWER` | `20` | RSI oversold threshold |
| `LOG_LEVEL` | `INFO` | Logging verbosity |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | Python 3.12, FastAPI, SQLAlchemy 2.0 (async), Alembic, APScheduler |
| **Frontend** | Vue 3, TypeScript, TailwindCSS v4, Vite, Vue Router, Axios |
| **Database** | PostgreSQL 16 |
| **Data Sources** | Binance API (OHLCV), CoinGecko (metadata) |
| **AI/LLM** | Anthropic Claude API |
| **Analysis** | pandas, Z-score anomaly detection, RSI, MACD, Bollinger Bands |

---

## Anomaly Detection

SignalForge uses a pluggable detector architecture. Each detector implements the `BaseDetector` interface and produces scored `AnomalyCandidate` results:

| Detector | What it catches | Method |
|----------|----------------|--------|
| **Price Spike** | Unusual price movements | Z-score on close prices |
| **Volume Spike** | Abnormal trading volume | Z-score on volume |
| **RSI Extreme** | Overbought/oversold conditions | RSI-14 threshold breach |

Severity is automatically assigned based on score: `low` (< 0.6) / `medium` (0.6-0.75) / `high` (0.75-0.9) / `critical` (> 0.9).

---

## Development

```bash
# Run tests
cd backend && uv run pytest

# Lint
cd backend && uv run ruff check .

# Smoke test (requires running backend)
python scripts/smoke_test.py
```

---

## Roadmap

- [ ] User authentication & multi-tenant support
- [ ] Watchlists & personalized notifications
- [ ] WebSocket real-time price streaming
- [ ] Advanced ML-based anomaly detection (Isolation Forest, LSTM)
- [ ] Portfolio tracking & P&L analytics
- [ ] Mobile-responsive dashboard improvements
- [ ] Payment integration for premium features

---

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
