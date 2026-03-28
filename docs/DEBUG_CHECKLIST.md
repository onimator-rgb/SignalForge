# MarketPulse AI — Debug Checklist

When something isn't working, start here.

## Backend nie zwraca danych

```
1. curl http://localhost:8000/api/v1/health
   → connection refused? Backend nie dziala.
   → "degraded"? DB nie odpowiada. Sprawdz czy PostgreSQL dziala:
     psql -U marketpulse -d marketpulse -c "SELECT 1;"

2. curl http://localhost:8000/api/v1/assets
   → items=[]? Brak assets. Uruchom: cd backend && uv run python -m scripts.seed_assets

3. curl http://localhost:8000/api/v1/diagnostics/config
   → Sprawdz: database_connected, scheduler_enabled
```

## Ingestion nie dziala

```
1. curl http://localhost:8000/api/v1/diagnostics/config
   → scheduler_enabled=false? Ustaw SCHEDULER_ENABLED=true w .env i restartuj.

2. curl http://localhost:8000/api/v1/ingestion/status
   → recent_jobs puste? Scheduler nie uruchomil zadnego joba.
   → status=failed? Sprawdz error_summary.

3. curl http://localhost:8000/api/v1/diagnostics/sync
   → "no_data"? Nigdy nie ingestowano. Reczny trigger:
     curl -X POST http://localhost:8000/api/v1/ingestion/trigger \
       -H "Content-Type: application/json" -d '{"interval":"1h","asset_symbols":["BTC"]}'

4. Binance dostepny?
   curl "https://api.binance.com/api/v3/ping"
```

## Asset ma stare dane

```
1. curl http://localhost:8000/api/v1/diagnostics/sync
   → Znajdz asset, sprawdz minutes_ago i status.
   → "stale"? Ingestion dziala ale ten asset failuje.
   → Sprawdz last_error i consecutive_errors.

2. Sprawdz binance_symbol:
   curl "https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1h&limit=1"
```

## Anomalie sie nie pojawiaja

```
1. curl http://localhost:8000/api/v1/anomalies/stats
   → total=0? Prawdopodobnie thresholdy za wysokie lub za malo danych.

2. curl http://localhost:8000/api/v1/diagnostics/config
   → Sprawdz anomaly_thresholds. Progi domyslne: price=2.5, volume=3.0

3. curl http://localhost:8000/api/v1/price-bars/count
   → Potrzeba min. 50 barow 1h (50h danych) dla price spike.

4. Obniz thresholdy tymczasowo:
   ANOMALY_PRICE_ZSCORE_THRESHOLD=1.5
   ANOMALY_VOLUME_ZSCORE_THRESHOLD=1.5
   Restart → trigger ingestion → sprawdz anomalies.
```

## Frontend pokazuje pusty ekran

```
1. DevTools → Console → szukaj [API] errors.
   → Zanotuj request_id z error message.

2. DevTools → Network → sprawdz HTTP responses.
   → 502/503? Backend nie dziala.
   → CORS error? Sprawdz backend CORS config.

3. Czy backend odpowiada?
   curl http://localhost:8000/api/v1/health
```

## Request konczy sie 500

```
1. Odczytaj request_id z response (header X-Request-ID lub body).
2. Szukaj w logach backendu: grep {request_id}
3. Znajdz log "request.error" lub "request.unhandled_error" z traceback.
4. curl http://localhost:8000/api/v1/diagnostics/errors
   → Pokazuje ostatnie bledy z request_id.
```

## Scheduler nie uruchamia jobow

```
1. Logi przy starcie: szukaj "scheduler.started" lub "scheduler.disabled".
2. curl http://localhost:8000/api/v1/diagnostics/config
   → scheduler_enabled: true/false?
3. Czy backend byl restartowany po zmianie .env?
4. Logi: szukaj "scheduler.job_trigger" co 5 min.
```

## Diagnostics endpoints

| Endpoint | Co sprawdza |
|----------|------------|
| `GET /api/v1/health` | DB connection, app version |
| `GET /api/v1/diagnostics/sync` | Per-asset data freshness |
| `GET /api/v1/diagnostics/config` | Current settings (safe subset) |
| `GET /api/v1/diagnostics/errors` | Recent errors from memory |
| `GET /api/v1/ingestion/status` | Recent jobs + sync states |
| `GET /api/v1/anomalies/stats` | Anomaly counts by type/severity |
