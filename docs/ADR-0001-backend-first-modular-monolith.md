# ADR 0001: Backend-First Modular Monolith

## Status

Accepted

## Context

Project Defense AI needs a reliable daily loop before it needs distributed infrastructure complexity. The essential product behavior is:

- assign daily tasks
- accept submissions
- evaluate code/transcripts
- create mentor summaries
- require mentor approval before feedback release

The long-term platform may use independently deployable services, but the first milestone benefits from faster iteration, local testability, and a single domain model.

## Decision

Start with a FastAPI modular monolith. Keep strict boundaries between API, domain schemas, services, integrations, orchestration, and persistence. Use an in-memory repository only for the first local slice; production persistence is PostgreSQL with pgvector.

## Alternatives Considered

- Microservices from day one: better isolation, but too much operational overhead before the core workflow is validated.
- Frontend-first build: visually impressive, but risks creating screens before the domain contracts are correct.
- Script-only automation: fastest prototype, but weak auditability and poor path to a multi-tenant platform.

## Consequences

- The system can run and test locally immediately.
- Module boundaries can be split later into workers or services.
- Persistence adapters must replace the in-memory repository before real deployment.
- All AI decisions must remain structured, auditable, and mentor-reviewed.

