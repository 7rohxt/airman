.PHONY: help build up down logs test clean ingest roster eval

help:
	@echo "AIRMAN Dispatch System - Make commands:"
	@echo "  make build      - Build Docker images"
	@echo "  make up         - Start all services"
	@echo "  make down       - Stop all services"
	@echo "  make logs       - Tail logs from all containers"
	@echo "  make test       - Run all tests"
	@echo "  make clean      - Remove containers and volumes"
	@echo "  make ingest     - Run ingestion job"
	@echo "  make roster     - Generate sample roster"
	@echo "  make eval       - Run evaluation harness"

build:
	docker-compose build

up:
	docker-compose up -d
	@echo "Waiting for services to be ready..."
	@sleep 5
	@echo "API running at http://localhost:8000"
	@echo "API docs at http://localhost:8000/docs"

down:
	docker-compose down

logs:
	docker-compose logs -f

test:
	python app/ingestion/test_dry_run.py
	python app/scheduling/test_roster.py
	python app/dispatch/test_dispatch.py
	python app/rag/test_rag.py

clean:
	docker-compose down -v
	rm -f airman.db airman.db-journal
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

ingest:
	curl -X POST http://localhost:8000/ingest/run | jq

roster:
	curl -X POST http://localhost:8000/roster/generate \
	  -H "Content-Type: application/json" \
	  -d '{"week_start":"2025-07-07","base_icao":"VOBG","use_mock_weather":true,"weather_scenario":"good"}' \
	  | jq

eval:
	curl -X POST http://localhost:8000/eval/run | jq