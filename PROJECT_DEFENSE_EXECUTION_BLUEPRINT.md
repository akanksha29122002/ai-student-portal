# Project Defense AI - Execution Blueprint

## What We Are Building

Project Defense AI is a daily preparation and automated first-review system for engineering students who already have a project and are preparing for project defense interviews.

It turns a vague instruction like "improve your project before the interview" into a daily operating system:

- Students receive daily coding tasks and spoken explanation questions.
- Students submit GitHub commits or transcript links.
- The system evaluates submissions automatically.
- Mentors receive a short daily summary.
- Mentors make the final call and release feedback.
- Missed work and weak progress are caught early.

## MVP Workflow

1. Admin creates an organization, program, and batch.
2. Mentor adds Track A students.
3. Student connects or submits a GitHub repository.
4. Mentor or AI creates a preparation plan:
   - coding actionables
   - 10 defense questions
   - daily schedule
5. System assigns daily tasks.
6. Student submits:
   - commit or PR for coding tasks
   - transcript link or transcript text for spoken questions
7. Worker evaluates the submission.
8. AI stores structured verdict, score, confidence, evidence, and feedback draft.
9. Mentor reviews the AI result.
10. Mentor approves, edits, or overrides the result.
11. Student receives mentor-approved feedback.
12. System flags students who miss 3 consecutive days.

## Recommended Architecture

Use a modular monolith for the MVP. It is faster to build, easier to debug, and still scalable when module boundaries are clean.

Core modules:

- identity
- organizations
- programs
- students
- projects
- tasks
- submissions
- evaluations
- ai_orchestration
- mentor_reviews
- notifications
- analytics
- audit

Deployment units:

- web frontend
- backend API
- background worker
- PostgreSQL
- Redis

## Backend API Areas

- `/health`
- `/auth`
- `/organizations`
- `/programs`
- `/batches`
- `/students`
- `/projects`
- `/repositories`
- `/preparation-plans`
- `/tasks`
- `/submissions`
- `/evaluations`
- `/mentor-reviews`
- `/daily-summaries`
- `/notifications`

## Core Status Lifecycles

### Submission

- received
- queued
- processing
- evaluated
- mentor_review_pending
- feedback_released
- failed

### Evaluation

- pending
- completed
- validation_failed
- needs_human_review
- superseded

### Mentor Review

- pending
- approved
- edited
- overridden
- returned_for_revision

## Scoring Model

Use 0 to 100 scores.

Coding task rubric:

- task relevance: 20
- correctness: 25
- integration with project: 20
- code quality: 15
- security: 10
- maintainability: 10

Transcript rubric:

- technical accuracy: 25
- project specificity: 20
- architecture understanding: 20
- tradeoff reasoning: 15
- clarity: 10
- confidence: 10

Readiness tiers:

- 85 to 100: interview ready
- 70 to 84: mostly ready
- 50 to 69: needs mentor support
- 0 to 49: high risk

## Daily Summary Format

Mentor summary should answer four questions:

- Who is on track?
- Who needs review?
- Who missed submission?
- What should the mentor do today?

Keep the default summary under one page. Put detailed evidence behind a drill-down.

## Agent Contracts

Every agent must:

- accept typed inputs
- return schema-valid JSON
- include confidence
- include evidence
- include failure reasons
- support retries
- store prompt version
- store raw model output separately from validated output
- fail closed when confidence is too low

## Human Safety Rules

- AI cannot pass or fail a student.
- AI cannot send final feedback without mentor approval.
- AI cannot hide evidence from mentors.
- AI must flag uncertainty.
- Mentor overrides must be audited.

## Integrations

### GitHub

Required:

- parse commit and PR URLs
- fetch diff
- fetch changed files
- detect trivial changes
- compare against task acceptance criteria
- store commit metadata

Later:

- OAuth GitHub
- repository indexing
- webhook ingestion

### Google Transcript

MVP:

- accept transcript text or accessible document link
- store extracted plain text
- evaluate against assigned questions

Later:

- Google OAuth
- Google Drive API
- Meet transcript import automation

### Forms

MVP can use internal submission forms.

If Google Forms is used temporarily:

- import rows from Google Sheets
- normalize data into submissions
- validate missing/invalid links

## Database Priorities

Must support:

- multi-tenant organization isolation
- daily batch queries
- student progress history
- mentor review history
- AI auditability
- prompt version history
- event replay or at least event audit

Use PostgreSQL first. Use pgvector for embeddings because it keeps relational data and semantic search together for the MVP.

## Testing Priorities

Start with:

- API health test
- model import test
- submission validation tests
- commit URL parser tests
- scoring schema validation tests
- mentor override audit test

Add later:

- GitHub integration tests
- transcript evaluation tests
- AI regression tests
- load tests for batch summary generation

## Product Screens

### Student

- Today task
- Submission form
- Previous feedback
- Progress timeline
- Interview countdown

### Mentor

- Daily summary
- Flagged students
- Evaluation detail
- Evidence panel
- Approve/edit/override feedback
- Missed submission list

### Program Manager

- Batch readiness
- Submission compliance
- Weak topics
- Upcoming interviews
- Mentor workload

### Admin

- Organization settings
- Users and roles
- Program setup
- Batch setup
- Integration settings

## Build Order

1. Domain documentation and architecture decisions.
2. Backend foundation.
3. Authentication and organization model.
4. Program, batch, student, project model.
5. Daily task and submission engine.
6. Evaluation schema and worker pipeline.
7. Mentor review workflow.
8. Student feedback workflow.
9. Reminder automation.
10. Analytics dashboards.

## Definition of Done

A milestone is done only when:

- code is implemented
- database migrations exist
- tests cover critical behavior
- API schemas are typed
- errors are handled
- audit records are written where needed
- documentation is updated
- the system can be run locally

## Immediate Next Build Instruction

Begin with a backend-first MVP. Create the foundations required for the core daily loop:

- Track A student
- preparation plan
- daily task
- submission
- AI evaluation record
- mentor review
- feedback release

Keep the first build boring, typed, testable, and ready to extend. The magic belongs in the workflow and evaluation quality, not in unnecessary infrastructure complexity.
