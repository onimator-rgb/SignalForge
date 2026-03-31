# SignalForge — Deployment Guide

## Docker Compose (recommended)

### Prerequisites
- Docker + Docker Compose
- `.env` file configured (copy from `.env.example`)

### Start

```bash
cp .env.example .env
# Edit .env — set ANTHROPIC_API_KEY, SCHEDULER_ENABLED=true

docker compose up -d --build
```

### Access

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| API Docs | http://localhost:8000/docs |

### First run — seed data

```bash
# Run migrations
docker compose exec backend uv run alembic upgrade head

# Seed assets
docker compose exec backend uv run python -m scripts.seed_assets
docker compose exec backend uv run python -m scripts.seed_stocks

# Trigger initial ingestion
docker compose exec backend python -c "
import urllib.request, json
for ac in ['crypto', 'stock']:
    req = urllib.request.Request('http://localhost:8000/api/v1/ingestion/trigger',
        data=json.dumps({'asset_class': ac, 'interval': '1h'}).encode(),
        headers={'Content-Type': 'application/json'}, method='POST')
    print(json.loads(urllib.request.urlopen(req).read())['message'])
"
```

### Check health

```bash
# All services
docker compose ps

# Backend health
curl http://localhost:8000/api/v1/health

# Runtime status
curl http://localhost:8000/api/v1/runtime-status

# Scheduler jobs
curl http://localhost:8000/api/v1/runtime-status | python -m json.tool
```

### View logs

```bash
# All
docker compose logs -f

# Backend only
docker compose logs -f backend

# Last 100 lines
docker compose logs --tail=100 backend
```

### Stop

```bash
docker compose down
```

### Stop + remove data

```bash
docker compose down -v
```

### Recovery

```bash
# Evaluate pending recommendations
curl -X POST http://localhost:8000/api/v1/recovery/evaluate-pending

# Run watchdog
curl -X POST http://localhost:8000/api/v1/recovery/run-watchdog

# Runtime doctor (if running locally)
cd backend && uv run python -m scripts.runtime_doctor
```

### Restart backend only

```bash
docker compose restart backend
```

---

## Local development (without Docker)

### Prerequisites
- Python 3.12+, Node.js 18+, PostgreSQL 16+, uv

### Start

```bash
# Backend
cd backend
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000

# Frontend (separate terminal)
cd frontend
npm install
npm run dev
```

Frontend at http://localhost:5173, Backend at http://localhost:8000.

---

## Configuration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | Yes | `postgresql+asyncpg://...` | PostgreSQL connection |
| `SCHEDULER_ENABLED` | No | `false` | Enable periodic ingestion |
| `ANTHROPIC_API_KEY` | For reports | — | Claude API key |
| `STRATEGY_PROFILE` | No | `balanced` | conservative/balanced/aggressive |
| `LOG_LEVEL` | No | `INFO` | Logging verbosity |

---

## Persistence

| Data | Storage | Persistent |
|------|---------|-----------|
| PostgreSQL | Docker volume `pgdata` | Yes |
| Live price cache | In-memory | No (rebuilt on start) |
| Runtime heartbeats | PostgreSQL | Yes |
| Scheduler state | In-memory | No (jobs restart on boot) |

---

## Architecture in Docker

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   Frontend   │────>│   Backend    │────>│  PostgreSQL   │
│   :3000      │     │   :8000      │     │   :5432       │
│   (serve)    │     │   (uvicorn)  │     │   (volume)    │
└──────────────┘     └──────────────┘     └──────────────┘
                            │
                     ┌──────┴──────┐
                     │  Binance WS │
                     │  Yahoo poll │
                     │  Claude API │
                     └─────────────┘
```
