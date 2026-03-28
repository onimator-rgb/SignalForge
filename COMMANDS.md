# SignalForge — Command Reference

## Prerequisites

```bash
python scripts/check_prerequisites.py
```

## Database (local PostgreSQL)

```bash
psql -U postgres -c "CREATE USER marketpulse WITH PASSWORD 'marketpulse';"
psql -U postgres -c "CREATE DATABASE marketpulse OWNER marketpulse;"
```

## Backend

```bash
cd backend
uv sync                                            # Install dependencies
uv run alembic upgrade head                        # Run migrations
uv run python -m scripts.seed_assets               # Seed 25 crypto assets
uv run python -m scripts.seed_stocks               # Seed 15 US stocks
uv run uvicorn app.main:app --reload --port 8000   # Start backend
```

## Frontend

```bash
cd frontend
npm install
npm run dev
```

## Ingestion

```bash
# Crypto
curl -X POST http://localhost:8000/api/v1/ingestion/trigger \
  -H "Content-Type: application/json" -d '{"asset_class":"crypto","interval":"1h"}'

# Stocks
curl -X POST http://localhost:8000/api/v1/ingestion/trigger \
  -H "Content-Type: application/json" -d '{"asset_class":"stock","interval":"1h"}'
```

## Verification

```bash
python scripts/smoke_test.py                       # API smoke test
cd backend && uv run python -m scripts.sanity_check  # DB sanity check
curl http://localhost:8000/api/v1/health             # Health check
```

## Key endpoints

```bash
curl http://localhost:8000/api/v1/dashboard/overview         # Dashboard aggregate
curl http://localhost:8000/api/v1/recommendations/active     # Active signals
curl http://localhost:8000/api/v1/recommendations/performance # Engine accuracy
curl http://localhost:8000/api/v1/portfolio                   # Demo portfolio
curl http://localhost:8000/api/v1/live/prices                 # Live/cached prices
curl http://localhost:8000/api/v1/diagnostics/sync            # Data freshness
curl http://localhost:8000/api/v1/diagnostics/errors          # Recent errors
```
