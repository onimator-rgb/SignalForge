.PHONY: db-create migrate migrate-revision seed backend-dev frontend-dev health smoke-test

# Database (local PostgreSQL)
db-create:
	psql -U postgres -c "CREATE USER marketpulse WITH PASSWORD 'marketpulse';" || true
	psql -U postgres -c "CREATE DATABASE marketpulse OWNER marketpulse;" || true

# Backend
backend-dev:
	cd backend && uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

migrate:
	cd backend && uv run alembic upgrade head

migrate-revision:
	cd backend && uv run alembic revision --autogenerate -m "$(msg)"

migrate-downgrade:
	cd backend && uv run alembic downgrade -1

seed:
	cd backend && uv run python -m scripts.seed_assets

# Frontend
frontend-dev:
	cd frontend && npm run dev

# Verification
health:
	curl -s http://localhost:8000/api/v1/health | python -m json.tool

smoke-test:
	python scripts/smoke_test.py
