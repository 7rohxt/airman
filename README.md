# AIRMAN — Skynet Dynamic Roster + Dispatch

AI-powered flight scheduling and dispatch system for flight training operations.

[![CI/CD](https://github.com/7rohxt/airman-dispatch/actions/workflows/ci-cd.yml/badge.svg)](https://github.com/7rohxt/airman-dispatch/actions)

## Features

- **Automated Ingestion**: Idempotent loading of students, instructors, aircraft, simulators, and rules
- **Constraint-Based Roster Generation**: 7-day schedule with zero hard constraint violations
- **Weather-Aware Dispatch**: Real-time GO/NO-GO decisions with METAR integration
- **Intelligent SIM Conversion**: Automatic fallback to simulator training when weather is below minima
- **RAG-Powered Explainability**: Every decision cites the specific rule from policy documents
- **REST API**: FastAPI with Swagger docs at `/docs`
- **Docker Compose**: One-command deployment

## Quick Start

```bash
# Start all services
docker-compose up -d --build

# API available at: http://localhost:8000/docs
```

## Architecture

```
FastAPI Endpoints → Ingestion | Roster Gen | Weather | Dispatch | RAG
                         ↓
                   PostgreSQL + Redis
```

## API Endpoints

- `POST /ingest/run` - Load bucket data
- `POST /roster/generate` - Generate 7-day roster
- `POST /dispatch/recompute` - Update decisions with fresh weather
- `POST /eval/run` - Run 25 test scenarios

## Testing

```bash
make test
```

## Evaluation

25 scenarios covering weather variations, maintenance windows, and availability changes.

```bash
python eval/generate_scenarios.py
curl -X POST http://localhost:8000/eval/run
```

See [PLAN.md](PLAN.md), [CUTS.md](CUTS.md), and [POSTMORTEM.md](POSTMORTEM.md) for details.