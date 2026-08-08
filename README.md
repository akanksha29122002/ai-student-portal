# Project Defense AI

Project Defense AI is a backend-first platform for daily project-defense preparation. It assigns daily coding and spoken explanation tasks, accepts student submissions, prepares structured AI evaluation records, and keeps mentors in control of final feedback.

## Current Milestone

This repository currently implements the foundation for the core daily loop:

- health check API
- organization, batch, student, project, task, submission, evaluation, and mentor review schemas
- typed event envelope
- in-memory development repository
- deterministic evaluation bootstrap service
- FastAPI routes for creating and reviewing the daily workflow
- tests for health, schemas, and service behavior

## Run Locally

```powershell
python -m uvicorn app.main:app --reload
```

Open:

- API: `http://127.0.0.1:8000`
- Docs: `http://127.0.0.1:8000/docs`
- Health: `http://127.0.0.1:8000/health`

## Test

```powershell
python -m pytest
```

## Architecture Direction

The MVP starts as a modular monolith. This keeps the first production loop simple to run while preserving clean module boundaries for later extraction into services or workers.

Production path:

- FastAPI API
- PostgreSQL with pgvector
- Redis-backed background jobs
- GitHub and transcript ingestion adapters
- AI orchestration layer with prompt versioning and JSON schema validation
- mentor approval workflow before student-visible feedback

