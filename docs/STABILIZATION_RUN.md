# Stabilization Run — Full Platform

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

Look for in logs:
- `scheduler_started` — scheduler active
- `live_prices.stream_start` — live price pollers running
- `scheduled_ingestion_done asset_class=crypto` — first crypto cycle
- `scheduled_ingestion_done asset_class=stock` — first stock cycle
- `recommendation.batch_done` — recommendations generated
- `portfolio.evaluate_done` — portfolio checked

---

## Sanity check (no backend needed)

```bash
cd backend && uv run python -m scripts.sanity_check
```

## Smoke test (backend must be running)

```bash
python scripts/smoke_test.py
```

---

## Key monitoring commands

### Health & diagnostics

```bash
curl -s http://localhost:8000/api/v1/health | python -m json.tool
curl -s http://localhost:8000/api/v1/diagnostics/sync | python -m json.tool
curl -s http://localhost:8000/api/v1/diagnostics/errors | python -m json.tool
curl -s http://localhost:8000/api/v1/diagnostics/config | python -m json.tool
```

### Dashboard overview (aggregate)

```bash
curl -s http://localhost:8000/api/v1/dashboard/overview | python -m json.tool
```

### Assets

```bash
curl -s "http://localhost:8000/api/v1/assets?asset_class=crypto&limit=3" | python -m json.tool
curl -s "http://localhost:8000/api/v1/assets?asset_class=stock&limit=3" | python -m json.tool
```

### Manual ingestion

```bash
# Crypto
curl -s -X POST http://localhost:8000/api/v1/ingestion/trigger \
  -H "Content-Type: application/json" -d '{"asset_class": "crypto", "interval": "1h"}'

# Stocks
curl -s -X POST http://localhost:8000/api/v1/ingestion/trigger \
  -H "Content-Type: application/json" -d '{"asset_class": "stock", "interval": "1h"}'
```

### Recommendations & performance

```bash
curl -s http://localhost:8000/api/v1/recommendations/active | python -m json.tool
curl -s http://localhost:8000/api/v1/recommendations/performance | python -m json.tool
```

### Portfolio

```bash
curl -s http://localhost:8000/api/v1/portfolio | python -m json.tool
curl -s -X POST http://localhost:8000/api/v1/portfolio/evaluate | python -m json.tool
```

### Live prices

```bash
curl -s http://localhost:8000/api/v1/live/prices | python -m json.tool
```

### Alerts & anomalies

```bash
curl -s http://localhost:8000/api/v1/anomalies/stats | python -m json.tool
curl -s http://localhost:8000/api/v1/alerts/stats | python -m json.tool
```

---

## Monitoring checklist (during 24-72h run)

### Every 1 hour
- [ ] Health OK
- [ ] Ingestion jobs completing (check logs)
- [ ] No persistent sync errors

### Every 4 hours
- [ ] Dashboard overview — equity, signals, anomalies reasonable
- [ ] Price bars growing for both crypto and stocks
- [ ] Recommendations regenerating (superseding old ones)

### Every 12 hours
- [ ] Portfolio: check open positions PnL
- [ ] Evaluation: check if 24h evaluations started appearing
- [ ] Live prices: check cache vs fallback ratio
- [ ] Frontend: all views load without errors

### After 24 hours
- [ ] Evaluation: `evaluated_24h > 0` in performance endpoint
- [ ] Portfolio: at least some position activity (open/close)
- [ ] Recommendation accuracy: first forward-return data available

### After 72 hours
- [ ] Evaluation: `evaluated_72h > 0`
- [ ] Score calibration review: v1 vs v2 comparison possible
- [ ] Portfolio: meaningful win/loss data

---

## Red flags

- `scheduler_disabled` in logs → check .env
- `assets_fail > 5` → provider issue
- `consecutive_errors > 3` → check that symbol
- Stock stale during market hours → diagnostics bug
- `500` errors on any endpoint → check backend logs
- Portfolio equity drops below $800 → review positions
- 0 recommendations after ingestion → scoring bug
- Live prices all "fallback" → poller not working

---

## Exit criteria (ready for next phase)

- [ ] Backend stable 24h+ without crashes
- [ ] 50+ ingestion cycles completed (crypto + stock)
- [ ] Health OK, errors < 10
- [ ] Recommendations: evaluated_24h count > 0
- [ ] Portfolio: at least 1 open + 1 closed position
- [ ] Live prices: >50% from cache (not fallback)
- [ ] Dashboard loads with all widgets populated
- [ ] Smoke test passes
- [ ] No persistent sync errors
