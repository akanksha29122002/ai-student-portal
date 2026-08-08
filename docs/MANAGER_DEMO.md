# Project Defense AI — Manager Presentation

## Problem

Engineering bootcamps evaluate 20–50 students daily on coding tasks. Today, mentors:
- Read every submission manually (20–40 min per student)
- Apply inconsistent rubrics
- Cannot scale beyond 15–20 students per mentor
- Have no structured evidence for why a student passed or failed

**Result:** Bottleneck on mentors, inconsistent feedback, slow student improvement loops.

---

## Solution

Project Defense AI automates the first pass of every submission evaluation using an AI pipeline that:

1. Reads the task requirements and acceptance criteria
2. Fetches the student's GitHub commit
3. Evaluates code across five dimensions using a weighted rubric
4. Produces a structured score, evidence, and rationale
5. Flags submissions that need human attention
6. Hands the mentor a pre-analyzed case — approve, request changes, or override

**Mentors go from reading code to reviewing AI analysis.**

---

## What You're Looking At

The demo running at `http://localhost:3000` is a full end-to-end system:

| Layer | Technology | Status |
|-------|-----------|--------|
| Backend API | FastAPI (Python) | 325 tests passing |
| Authentication | JWT + refresh tokens + RBAC | Production-grade |
| Event bus | In-process async event system | Milestone 4 |
| AI pipeline | Evaluation engine with 5-dimension rubric | Milestone 5 |
| Frontend | Next.js 15 + TypeScript + Tailwind | Milestone 6 |

---

## Workflow

```
Student → Submit commit URL
   ↓
AI Pipeline (real-time, ~2–5 seconds)
   ├─ Context builder: reads task + GitHub commit
   ├─ Evaluator: scores 5 dimensions via LLM
   └─ Validator: checks confidence, flags for review
   ↓
Structured result: score + criteria + issues + strengths
   ↓
Mentor dashboard → 1-click review → decision recorded
```

---

## Key Metrics (demo data)

- 5 students, 5 tasks, 4 evaluations pre-seeded
- Average evaluation time: ~2–5 seconds (Mock AI) / 15–30 seconds (Anthropic Claude)
- Mentor review time: ~30 seconds per evaluation
- Estimated time saving: 15–20 min per student per day

---

## Architecture

```
frontend/                   Next.js App Router
  app/
    login/                  JWT auth + demo quick-login
    student/                Task view, submit, result
    mentor/                 Dashboard, evaluations, review

app/                        FastAPI backend
  api/
    auth/                   /auth/token, /auth/me, /auth/refresh
    submissions/            POST/GET submissions
    evaluations/            GET evaluations, POST mentor-review
    tasks/                  GET tasks
    frontend_router/        /me/*, /students/*, /batches/*
  ai/
    engine.py               Evaluation pipeline
    provider.py             Anthropic / MockAI adapter
  services/
    store.py                InMemoryStore (production: PostgreSQL)
  scripts/
    seed_demo.py            Demo data seeder
```

---

## Roadmap

### Milestone 7 (Next)
- PostgreSQL persistence (replace InMemoryStore)
- Real GitHub API integration (commit diff, file contents)
- Batch scheduling (assign tasks to cohorts by date)

### Milestone 8
- Student progress history (score trends over time)
- Mentor analytics (cohort performance, common failure patterns)
- Email notifications (evaluation complete, mentor review done)

### Milestone 9
- Multi-tenant organizations
- Custom rubric builder per task
- Anthropic Claude integration with configurable model

### Production path
- Docker Compose: backend + PostgreSQL + frontend
- Deploy to Railway / Render (backend) + Vercel (frontend)
- Estimated total: 3–4 additional engineering weeks

---

## Current Limitations

1. **In-memory storage** — data resets on server restart (PostgreSQL in Milestone 7)
2. **GitHub commits** — demo uses URL only; real diff fetching needs GitHub token
3. **MockAI** — demo uses deterministic mock responses; production needs Anthropic API key
4. **Single tenant** — one organization per deployment (multi-tenant in Milestone 9)

---

## How to Run

```bash
# Backend
cd ai-studnet-portal
set PROJECT_DEFENSE_DEMO_MODE=true    # Windows
# export PROJECT_DEFENSE_DEMO_MODE=true  # Mac/Linux
uvicorn app.main:app --reload --port 8000

# Frontend
cd ai-studnet-portal/frontend
npm run dev
# Open http://localhost:3000
```

Demo credentials: `student1@demo.projectdefense.ai` / `mentor@demo.projectdefense.ai` (password: `demo1234`)
