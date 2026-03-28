# MarketPulse AI — Command Reference

## Prerequisites check
```bash
python scripts/check_prerequisites.py
```

## Database (local PostgreSQL)
```bash
# First-time setup (run as postgres superuser):
psql -U postgres -c "CREATE USER marketpulse WITH PASSWORD 'marketpulse';"
psql -U postgres -c "CREATE DATABASE marketpulse OWNER marketpulse;"

# Verify connection:
psql -U marketpulse -d marketpulse -c "SELECT 1;"
```

## Backend
```bash
# Install dependencies
cd backend
uv sync

# Run migrations
cd backend
uv run alembic upgrade head

# Seed assets
cd backend
uv run python -m scripts.seed_assets

# Start dev server
cd backend
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Create new migration
cd backend
uv run alembic revision --autogenerate -m "description"
```

## Frontend
```bash
cd frontend
npm install
npm run dev
```

## Verification
```bash
# Health check
curl http://localhost:8000/api/v1/health

# Smoke test
python scripts/smoke_test.py

# API docs
# Open: http://localhost:8000/docs
```

## Ingestion
```bash
# Manual trigger (single asset)
curl -X POST http://localhost:8000/api/v1/ingestion/trigger \
  -H "Content-Type: application/json" \
  -d '{"interval": "1h", "asset_symbols": ["BTC"]}'

# Manual trigger (all assets)
curl -X POST http://localhost:8000/api/v1/ingestion/trigger \
  -H "Content-Type: application/json" \
  -d '{"interval": "1h"}'

# Check status
curl http://localhost:8000/api/v1/ingestion/status
```

## Diagnostics
```bash
curl http://localhost:8000/api/v1/diagnostics/sync     # Data freshness
curl http://localhost:8000/api/v1/diagnostics/config   # Current config
curl http://localhost:8000/api/v1/diagnostics/errors   # Recent errors
```
