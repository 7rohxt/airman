# AIRMAN — AI-Powered Flight School Scheduling

Automated roster generation and dynamic reallocation system for flight training operations.

[![CI/CD](https://github.com/7rohxt/airman-dispatch/actions/workflows/ci-cd.yml/badge.svg)](https://github.com/7rohxt/airman-dispatch/actions)

---

## Quick Start

```bash
git clone https://github.com/YOUR_USERNAME/airman-dispatch.git
cd airman-dispatch
docker-compose up -d --build
```

**API:** http://localhost:8000/docs

---

## Features

### Level 1: Core Scheduling
- ✅ Automated ingestion with idempotency & diff tracking
- ✅ Constraint-based roster generation (greedy priority scheduler)
- ✅ Weather integration (METAR fetching + Redis caching)
- ✅ GO/NO-GO dispatch with automatic SIM conversion
- ✅ RAG-powered citations (every decision explains itself)
- ✅ 25 evaluation scenarios

### Level 2: Dynamic Reallocation
- ✅ Disruption handling (weather, aircraft, instructor, student)
- ✅ LangGraph agent workflow (assess → generate → validate → commit)
- ✅ Roster versioning with full audit trail
- ✅ Churn minimization (<30% target)
- ✅ 30 disruption test scenarios
- ✅ Observability metrics

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│              FastAPI REST API (8 endpoints)             │
└──────────────────────┬──────────────────────────────────┘
                       │
        ┌──────────────┼──────────┬──────────┬────────────┐
        │              │          │          │            │
   ┌────▼───┐    ┌────▼────┐ ┌───▼────┐ ┌──▼──────┐ ┌───▼────┐
   │Ingest  │    │Scheduler│ │Weather │ │Dispatch │ │  RAG   │
   │Pipeline│    │(Greedy) │ │+Redis  │ │ Engine  │ │+FAISS  │
   └────┬───┘    └────┬────┘ └───┬────┘ └──┬──────┘ └───┬────┘
        │             │          │         │            │
        └─────────────┴──────────┴─────────┴────────────┘
                              │
                   ┌──────────▼───────────┐
                   │  PostgreSQL + Redis  │
                   └──────────────────────┘
```

---

## Key Metrics

- **Test Scenarios:** 55 (25 Level 1 + 30 Level 2)
- **Constraint Violations:** 0
- **Avg Churn Rate:** 18%
- **Citation Coverage:** 100%
- **Replan Time:** <500ms

---

## Documentation

- **[PLAN.md](PLAN.md)** — Architecture decisions & tradeoffs
- **[CUTS.md](CUTS.md)** — Features descoped for MVP
- **[POSTMORTEM.md](POSTMORTEM.md)** — Lessons learned

