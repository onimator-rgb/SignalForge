# Stabilization Run — Mixed-Asset MVP

## Quick start

### 1. Prepare .env

```
SCHEDULER_ENABLED=true
LOG_LEVEL=INFO
INGESTION_INTERVAL_MINUTES=5
```

### 2. Start backend (with log file)

```bash
mkdir -p logs
cd backend && uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 2>&1 | tee ../logs/backend.log
```

### 3. Start frontend

```bash
cd frontend && npm run dev
```

### 4. Verify startup

After backend starts, look for these lines in logs:
- `scheduler_started` — scheduler is active
- `scheduled_ingestion_done asset_class=crypto` — first crypto cycle
- `scheduled_ingestion_done asset_class=stock` — first stock cycle

---

## Sanity check (no backend needed)

```bash
cd backend && uv run python -m scripts.sanity_check
```

Shows: assets count, price bars, anomalies, alerts, reports, ingestion jobs, sync errors.

## Smoke test (backend must be running)

```bash
python scripts/smoke_test.py
```

Covers: health, crypto+stock assets, OHLCV, indicators, anomalies, alerts, reports, diagnostics.

---

## Key monitoring commands

### Health & diagnostics

```bash
curl -s http://localhost:8000/api/v1/health | python -m json.tool
curl -s http://localhost:8000/api/v1/diagnostics/sync | python -m json.tool
curl -s http://localhost:8000/api/v1/diagnostics/errors | python -m json.tool
curl -s http://localhost:8000/api/v1/diagnostics/config | python -m json.tool
```

### Assets (filtered)

```bash
# All
curl -s "http://localhost:8000/api/v1/assets?limit=5" | python -m json.tool
# Crypto only
curl -s "http://localhost:8000/api/v1/assets?asset_class=crypto&limit=5" | python -m json.tool
# Stocks only
curl -s "http://localhost:8000/api/v1/assets?asset_class=stock&limit=5" | python -m json.tool
```

### Manual ingestion trigger

```bash
# Crypto
curl -s -X POST http://localhost:8000/api/v1/ingestion/trigger \
  -H "Content-Type: application/json" \
  -d '{"asset_class": "crypto", "interval": "1h"}' | python -m json.tool

# Stocks
curl -s -X POST http://localhost:8000/api/v1/ingestion/trigger \
  -H "Content-Type: application/json" \
  -d '{"asset_class": "stock", "interval": "1h"}' | python -m json.tool
```

### Anomalies & alerts

```bash
curl -s http://localhost:8000/api/v1/anomalies/stats | python -m json.tool
curl -s http://localhost:8000/api/v1/alerts/stats | python -m json.tool
```

---

## Quick validation checklist

After 1 hour of running, verify:

- [ ] `GET /health` → `200 ok`
- [ ] `GET /diagnostics/config` → `scheduler_enabled: true`
- [ ] `GET /assets?asset_class=crypto` → has prices
- [ ] `GET /assets?asset_class=stock` → has prices
- [ ] `GET /anomalies/stats` → `total > 0`
- [ ] `GET /diagnostics/errors` → `total_buffered < 10`
- [ ] Frontend dashboard loads — mixed data visible
- [ ] AssetsView filter (All/Crypto/Stocks) works

## Red flags

- `scheduler_disabled` in startup logs → check `.env`
- `assets_fail > 5` in ingestion logs → provider issue
- `consecutive_errors > 3` in sync states → check that symbol
- Stock assets `stale` during market hours → diagnostics bug
- `500` errors on asset detail → check backend logs

## Exit criteria (ready for push)

- [ ] Backend stable 12h+ without crashes
- [ ] 20+ crypto ingestion cycles, 10+ stock cycles
- [ ] Health OK, errors < 10
- [ ] Prices visible for both crypto and stocks
- [ ] Anomalies detected for both classes
- [ ] Smoke test passes
- [ ] Frontend works: dashboard, assets, detail, anomalies, alerts
