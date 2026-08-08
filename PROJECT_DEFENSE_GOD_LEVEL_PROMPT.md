# Project Defense AI - God Level Build Prompt

## Operating Role

You are Codex acting as a senior autonomous product engineering team. Your job is to design and build Project Defense AI as a production-grade platform, not a demo, not a CRUD dashboard, and not a loose collection of scripts.

Represent the combined judgment of:

- Principal Software Architect
- Staff Backend Engineer
- AI Systems Engineer
- Product Designer
- Security Engineer
- DevOps Engineer
- Data Architect
- Engineering Manager

Be practical, exact, and implementation-driven. Build milestone by milestone. Do not generate the entire system in one uncontrolled pass.

## Product

Project name: Project Defense AI

Tagline: An autonomous AI platform for project evaluation, learning analytics, and interview readiness.

Mission: Automate the repetitive daily review work in an engineering project defense program while keeping mentors responsible for final judgment.

This platform is focused first on Track A students: students who already have a project and need structured daily preparation before Week 1 discussion and Week 2 final interview.

## Core Problem

Track A students currently receive broad advice such as "improve your project" and may disappear until the interview. Mentors discover weak progress too late. At scale, manually opening every GitHub commit, transcript, and form response every day is not sustainable.

The platform must convert interview preparation into a daily accountability system:

- Assign specific daily project improvement tasks.
- Assign spoken technical explanation questions.
- Collect submissions through a simple form or app workflow.
- Automatically evaluate GitHub commits and spoken transcripts.
- Produce short mentor-ready summaries.
- Flag missing, weak, fake, or risky submissions early.
- Let mentors review and approve all feedback before students see it.

## Non-Negotiable Product Principles

1. Human final authority
   The AI never makes the final pass/fail decision and never directly sends high-impact evaluation feedback to a student without mentor review.

2. Evidence-based evaluation
   Every AI verdict must cite evidence: commit files, diff hunks, transcript excerpts, rubric items, missing concepts, and confidence.

3. Structured outputs
   Every AI agent output must be valid JSON matching a versioned schema. No unstructured AI prose for internal decisions.

4. Asynchronous by default
   Submission intake should return quickly. Heavy work such as repository cloning, diff analysis, transcript parsing, embedding, scoring, and reporting must run in background jobs.

5. Start lean, scale cleanly
   The first build may support 20 to 200 students, but the architecture must have a clear path to 1,000, 10,000, and beyond without rewriting the domain model.

6. Build real workflows
   Do not build static dashboard screens. Every screen must support an actual user workflow.

## Primary Users

- Student: completes daily coding and spoken explanation tasks.
- Mentor: reviews AI summaries, adjusts verdicts, sends feedback, handles flags.
- Program Manager: monitors batches, interviews, attendance, and student readiness.
- Organization Admin: manages programs, batches, mentors, policies, and integrations.
- Super Admin: operates the SaaS platform across organizations.
- System/AI Agent: processes events, evaluates submissions, and prepares summaries.

## MVP Scope

The first production-worthy version must support:

- Organization, program, batch, mentor, and student management.
- Track A student onboarding.
- GitHub repository connection and commit submission.
- Daily task assignment.
- Spoken question assignment.
- Submission intake.
- GitHub commit evaluation.
- Transcript evaluation from submitted document text/link.
- Mentor daily summary.
- Mentor review and override.
- Student feedback release after mentor approval.
- Missed-submission tracking and 3-day reminder flag.
- Audit trail for AI and mentor decisions.

Do not start with enterprise extras that delay the core loop. Build the daily task-review-feedback loop first.

## Daily Student Workflow

Each Track A student receives a preparation plan before the interview window.

Daily task types:

1. Coding task
   The student receives only a project-related problem statement, acceptance criteria, and due date. No solution, no starter code, and no direct hints unless the mentor chooses to reveal them.

   Required submission fields:
   - student_id
   - task_id
   - repository_url
   - commit_url or pull_request_url
   - self_status: solved, partially_solved, not_solved
   - short_approach_note

2. Spoken question task
   The student receives 1 to 2 project-defense questions per day, or more if the interview window is short.

   Required submission fields:
   - student_id
   - task_id
   - question_ids
   - transcript_url or transcript_text
   - self_status: attempted, skipped

## AI Evaluation Requirements

### GitHub Commit Evaluation Agent

The agent must evaluate whether the submitted code change is real, relevant, and technically sound.

Inputs:

- Task problem statement
- Acceptance criteria
- Student repository metadata
- Commit or pull request diff
- Relevant project context retrieved from the knowledge base
- Prior submissions and mentor feedback when available

Reject or flag:

- Empty commits
- Formatting-only changes
- Comment-only changes
- README-only changes when code was required
- Variable renames without behavioral improvement
- Copy-paste code with no integration
- Code that does not address the assigned task
- Security regressions
- Broken tests or build failures
- Architecture violations
- Suspicious AI-generated generic implementation that ignores local patterns

Output JSON:

```json
{
  "schema_version": "github_commit_evaluation.v1",
  "verdict": "correct | partially_correct | incorrect | no_valid_submission | needs_human_review",
  "score": 0,
  "confidence": 0.0,
  "evidence": [
    {
      "type": "diff | file | test | repository_context",
      "reference": "string",
      "summary": "string"
    }
  ],
  "rubric": {
    "task_relevance": 0,
    "correctness": 0,
    "code_quality": 0,
    "integration_with_project": 0,
    "security": 0,
    "maintainability": 0
  },
  "flags": ["string"],
  "mentor_note": "string",
  "student_feedback_draft": "string",
  "recommended_next_action": "approve_feedback | request_revision | mentor_review_required"
}
```

### Transcript Evaluation Agent

The agent must judge whether a student can explain their own project clearly and accurately.

Inputs:

- Assigned question
- Expected answer rubric
- Transcript text
- Project context
- Prior explanation attempts

Evaluate:

- Technical accuracy
- Project-specific understanding
- Architecture understanding
- Ability to explain tradeoffs
- Clarity and structure
- Confidence
- Missing concepts
- Hallucinated or generic claims

Output JSON:

```json
{
  "schema_version": "transcript_evaluation.v1",
  "verdict": "strong | acceptable | partial | weak | no_valid_submission | needs_human_review",
  "score": 0,
  "confidence": 0.0,
  "covered_concepts": ["string"],
  "missing_concepts": ["string"],
  "evidence": [
    {
      "question_id": "string",
      "transcript_reference": "string",
      "summary": "string"
    }
  ],
  "communication": {
    "clarity": 0,
    "structure": 0,
    "specificity": 0,
    "confidence": 0
  },
  "follow_up_questions": ["string"],
  "mentor_note": "string",
  "student_feedback_draft": "string",
  "recommended_next_action": "approve_feedback | ask_follow_up | mentor_review_required"
}
```

### Mentor Summary Agent

The agent must compress daily activity into a mentor-readable operational summary.

Output JSON:

```json
{
  "schema_version": "mentor_daily_summary.v1",
  "organization_id": "string",
  "batch_id": "string",
  "date": "YYYY-MM-DD",
  "totals": {
    "students_expected": 0,
    "submitted": 0,
    "missing": 0,
    "strong": 0,
    "flagged": 0,
    "needs_human_review": 0
  },
  "students": [
    {
      "student_id": "string",
      "name": "string",
      "status": "on_track | flagged | missing | needs_review",
      "one_line_summary": "string",
      "recommended_mentor_action": "none | review_submission | send_reminder | schedule_check_in"
    }
  ],
  "batch_risks": ["string"],
  "mentor_actions": ["string"]
}
```

## System Architecture

Use a modular monolith first unless the repository already uses microservices. Keep module boundaries clean enough to split later.

Recommended stack:

- Frontend: Next.js, React, TypeScript, TailwindCSS, shadcn/ui.
- Backend: FastAPI, Python, SQLAlchemy, Alembic, Pydantic.
- Database: PostgreSQL with pgvector.
- Queue/cache: Redis plus Celery or equivalent worker system.
- Integrations: GitHub API, Google transcript ingestion, email provider.
- AI: LLM orchestration layer with prompt versioning, structured schemas, retries, confidence thresholds, and audit logs.
- Observability: structured logs, health checks, metrics, trace IDs.
- DevOps: Docker, Docker Compose, GitHub Actions, environment-based configuration.

Do not call LLMs directly from controllers. Route all AI work through an orchestration service.

## Event Model

Important events:

- StudentRegistered
- StudentOnboarded
- RepositoryConnected
- RepositoryIndexed
- PreparationPlanCreated
- DailyTaskAssigned
- SubmissionReceived
- CommitFetched
- CommitEvaluated
- TranscriptFetched
- TranscriptEvaluated
- DailySummaryGenerated
- MentorReviewedEvaluation
- FeedbackReleased
- SubmissionMissed
- ReminderTriggered
- InterviewScheduled
- InterviewCompleted

Each event must include:

- event_id
- event_type
- occurred_at
- organization_id
- actor_type
- actor_id
- correlation_id
- payload

## Data Model

Design normalized tables for:

- organizations
- users
- roles
- memberships
- programs
- batches
- students
- mentors
- projects
- repositories
- repository_snapshots
- knowledge_documents
- embeddings
- preparation_plans
- tasks
- task_questions
- submissions
- github_commit_evaluations
- transcript_evaluations
- mentor_reviews
- feedback
- reminders
- interviews
- daily_summaries
- audit_logs
- ai_prompt_versions
- ai_runs
- events

Include:

- UUID primary keys
- created_at and updated_at
- soft deletion where appropriate
- foreign keys
- indexes for daily summary queries
- unique constraints for one submission per student per task per day
- audit records for all AI and mentor decisions

## Frontend Experience

Build the actual product, not a landing page.

Required dashboards:

- Student dashboard: today task, pending submissions, progress, feedback, interview countdown.
- Mentor dashboard: daily summary, flagged students, review queue, feedback approval.
- Program manager dashboard: batch health, submission trends, readiness, missed submissions.
- Admin dashboard: users, batches, programs, integrations, policies.

Design direction:

- Dense, calm, professional workflow UI.
- Clear status indicators.
- Fast review actions.
- Tables for operational views.
- Drawer or detail panel for evidence review.
- Accessible responsive layout.
- Dark mode support only if the existing design system supports it cleanly.

## Security and Compliance

Implement:

- JWT access tokens and refresh tokens
- RBAC
- secure password hashing
- OAuth readiness for GitHub and Google
- input validation
- rate limiting
- CORS configuration
- secrets via environment variables
- audit trails
- signed or access-controlled transcript/document URLs
- tenant isolation by organization_id

Never expose raw secrets, tokens, private repository content, or private transcripts to unauthorized users.

## Development Milestones

Milestone 1: Product and domain model
- Clarify workflows.
- Define roles and permissions.
- Define events.
- Define MVP boundaries.

Milestone 2: Backend foundation
- FastAPI app structure.
- Configuration.
- Database connection.
- SQLAlchemy models.
- Alembic migrations.
- Health checks.
- Error handling.

Milestone 3: Authentication and organizations
- Users.
- Organizations.
- Memberships.
- Roles.
- Login, refresh, logout.
- Permission checks.

Milestone 4: Track A operations
- Programs.
- Batches.
- Students.
- Projects.
- Preparation plans.
- Daily task assignment.

Milestone 5: Submission engine
- Coding submission intake.
- Transcript submission intake.
- Idempotency.
- Validation.
- Submission status lifecycle.

Milestone 6: GitHub evaluation
- Commit URL parsing.
- Diff fetching.
- Repository context retrieval.
- Evaluation schema.
- Fake/trivial commit detection.
- AI scoring and audit.

Milestone 7: Transcript evaluation
- Transcript ingestion.
- Question rubric matching.
- AI scoring and audit.
- Follow-up question generation.

Milestone 8: Mentor review loop
- Daily summaries.
- Review queue.
- Override verdict.
- Approve feedback.
- Release feedback to student.

Milestone 9: Notifications and reminders
- Missed submission detection.
- 3-day reminder rule.
- Mentor flags.
- Email notifications.

Milestone 10: Analytics
- Batch health.
- Student readiness.
- Weak topics.
- Learning velocity.
- Interview readiness trends.

Milestone 11: Production readiness
- Tests.
- Docker.
- CI.
- Logging.
- Metrics.
- Deployment docs.
- Runbooks.

## Development Rules

- Before coding, inspect the existing repository structure.
- Follow existing conventions unless they are clearly broken.
- Keep every change scoped to the active milestone.
- Add tests for meaningful behavior.
- Avoid placeholders and fake implementations in core workflows.
- If a dependency or integration is unavailable, define an interface and implement a local adapter that can be replaced.
- Every API should have request and response schemas.
- Every background job should be idempotent.
- Every AI run should be persisted with prompt version, input hash, output JSON, confidence, and validation result.
- Mentor-facing summaries must be short. Evidence belongs in drill-down views.

## First Task for Codex

Start by building Milestone 1 and Milestone 2 only.

Deliver:

- A concise architecture decision record.
- Domain model and workflow documentation.
- Backend project structure.
- Database models and initial migrations.
- Health check endpoint.
- Development setup instructions.
- Tests proving the backend starts and core models can be imported.

Stop after Milestone 2 and report what is complete, what is verified, and what the next milestone should be.
