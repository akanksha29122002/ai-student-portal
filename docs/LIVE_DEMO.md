# LIVE APPLICATION

## URLs

**Frontend:** https://project-defense-ai.vercel.app

**Backend API:** https://project-defense-ai-api.onrender.com  
*(Note: Render free tier sleeps after 15 min idle — first request may take 30s)*

**API Docs:** https://project-defense-ai-api.onrender.com/docs

---

## Demo Credentials

**Student:**  
Email: `student1@demo.projectdefense.ai`  
Password: `demo1234`

**Mentor:**  
Email: `mentor@demo.projectdefense.ai`  
Password: `demo1234`

---

## 5-Minute Demo Flow

### Setup (30 seconds before demo)
1. Open https://project-defense-ai.vercel.app in Chrome
2. If you see a spinner, wait for Render backend to wake up (~30s)

---

### Part 1: Student Experience (2 minutes)

**Step 1** — The app redirects to `/login` automatically.

**Step 2** — Click **"Student Demo"** quick-login button.

**Step 3** — Student dashboard loads: 5 tasks, stats (submitted/pending).

**Step 4** — Click a task card → full problem statement, acceptance criteria, expected concepts.

**Step 5** — Click **"Submit Work"** → 3-field form: commit URL, approach, self-assessment.

**Step 6** — Fill in a GitHub URL (e.g. `https://github.com/demo/repo/commit/abc123`) and click **Submit for AI Evaluation**.

**Step 7** — Watch the 5-step evaluation animation: reading task → fetching commit → analysing files → checking criteria → evaluating.

**Step 8** — Result appears: **score badge (0–10)**, dimension bars, acceptance criteria pass/fail, issues found, strengths.

---

### Part 2: Mentor Experience (2 minutes)

**Step 9** — Click **Logout**, then **"Mentor Demo"** quick-login.

**Step 10** — Mentor dashboard: 4 stat cards (total students, submitted, needs review, avg score). "Requires Attention" cards highlighted in amber.

**Step 11** — Scroll to **All Students** table: 5 rows, each with AI score and review status.

**Step 12** — Click **"Review"** on a flagged student → full evaluation detail page.

**Step 13** — Show: score header, acceptance criteria, dimension scores (with AI reasoning), issues + file evidence, strengths, missing requirements.

**Step 14** — **Mentor Review form**: 4 decision buttons (Approve / Request Changes / Reject / Override Score).

**Step 15** — Select **"Request Changes"**, type feedback, click **Submit Review**.

**Step 16** — Green "Mentor Review Completed" banner. Decision recorded.

---

### Part 3: Scale (30 seconds)

> "This entire flow — from commit URL to structured AI evaluation with mentor review — runs in under 5 seconds using the mock AI. With a real Anthropic API key it uses Claude, taking 15–30 seconds for a full code analysis."

> "Behind this UI: 325 automated tests, JWT auth, RBAC, event bus, GitHub integration, and a 5-dimension AI rubric. Ready for PostgreSQL persistence in the next milestone."

---

## What to Say If Something Breaks

**Login fails:** "The backend may still be waking up — free tier sleeps. Let me refresh." Wait 30s and try again.

**Evaluation shows error:** "The mock AI evaluator is deterministic — let me use a pre-seeded evaluation instead." Navigate to Mentor → Evaluations and click an existing one.

**CORS error in browser console:** Backend is still starting — wait 30s and refresh.
