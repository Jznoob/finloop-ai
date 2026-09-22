.PHONY: install dev backend frontend test eval lint reset-db

install:
	python3 -m venv .venv
	.venv/bin/pip install -e 'backend[dev]'
	cd frontend && npm ci --cache ../.npm-cache

dev:
	./scripts/dev.sh

backend:
	.venv/bin/uvicorn app.main:app --app-dir backend --reload --port 8000

frontend:
	cd frontend && npm run dev

test:
	.venv/bin/pytest backend/tests -q
	cd frontend && npm test -- --run

eval:
	PYTHONPATH=backend .venv/bin/python -m app.evals

lint:
	.venv/bin/ruff check backend
	cd frontend && npm run lint

reset-db:
	./scripts/reset_db.sh
