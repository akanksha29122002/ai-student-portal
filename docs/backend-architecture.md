# Backend Architecture

## Folder Structure

```text
app/
  api/              HTTP routes and error translation
  application/      use cases, repository contracts, unit of work contracts
  core/             configuration and logging
  domain/           enums and domain events
  infrastructure/   database, SQLAlchemy models, repository adapters
  schemas/          API and domain transfer contracts
  services/         existing evaluation and in-memory services
  shared/           exceptions and cross-cutting primitives
  workers/          event-consuming worker foundations
```

## Architecture Diagram

```text
Client
  |
FastAPI Router
  |
Application Service
  |
Unit of Work ---- Event Store
  |
Repository Interfaces
  |
Infrastructure Repositories
  |
PostgreSQL / Redis / External Integrations
```

## ER Diagram

```text
organizations
  |-- programs
  |-- batches
        |-- students
              |-- projects
                    |-- repositories
              |-- daily_tasks
                    |-- submissions
                          |-- evaluations
                                |-- mentor_reviews
  |-- notifications
  |-- audit_logs
  |-- activity_logs
  |-- system_events
```

## Event Flow

```text
StudentRegistered -> ProjectCreated -> TaskAssigned -> SubmissionReceived
SubmissionReceived -> SubmissionValidated -> EvaluationStarted -> EvaluationCompleted
EvaluationCompleted -> DailySummaryGenerated -> MentorReviewed -> FeedbackReleased
SubmissionMissed -> ReminderTriggered
```

## Sequence Diagram

```text
Student -> API: POST /submissions
API -> DailyLoopService: create_submission
DailyLoopService -> UnitOfWork: begin
UnitOfWork -> SubmissionRepository: create
DailyLoopService -> EventStore: append SubmissionReceived
UnitOfWork -> Database: commit
Worker -> EventStore: consume SubmissionReceived
Worker -> EvaluationService: evaluate
Mentor -> API: POST /mentor-reviews
API -> DailyLoopService: create_mentor_review
DailyLoopService -> EventStore: append MentorReviewed
```

## Migration Strategy

Use Alembic for versioned database changes. Migrations are reviewed and committed with application code. Production rollout should run migrations before deploying API workers that depend on the new schema.

Commands:

```powershell
alembic upgrade head
alembic revision --autogenerate -m "describe change"
alembic downgrade -1
```

## Repository Pattern

Application services depend on repository protocols, not SQLAlchemy. Infrastructure adapters implement those protocols for in-memory development and PostgreSQL production. This keeps business workflows testable and prevents ORM queries from leaking into routers or domain code.

## Database Diagram

The first migration creates all core tables with UUID primary keys, timestamps, `deleted_at` soft-delete support, optimistic `version` columns, foreign keys, uniqueness constraints, and indexes for batch, student, submission, evaluation, and event queries.

