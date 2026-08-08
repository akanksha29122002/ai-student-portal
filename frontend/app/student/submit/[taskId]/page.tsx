"use client";
import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  getTask, getMySubmissions, getMyStudentProfile,
  createSubmission, triggerEvaluation,
} from "@/lib/api";
import { Task, Submission, EvaluationResponse } from "@/lib/types";
import { EvidenceCard } from "@/components/EvidenceCard";
import { DimensionBar } from "@/components/DimensionBar";
import { ScoreBadge } from "@/components/ScoreBadge";
import { StatusChip } from "@/components/StatusChip";

type Step = "form" | "evaluating" | "result";

const EVAL_STEPS = [
  "Reading task requirements",
  "Fetching commit",
  "Analysing changed files",
  "Checking acceptance criteria",
  "Evaluating implementation",
];

export default function SubmitPage() {
  const { taskId } = useParams<{ taskId: string }>();
  const router = useRouter();

  const [task, setTask] = useState<Task | null>(null);
  const [existingSubmission, setExistingSubmission] = useState<Submission | null>(null);
  const [evaluation, setEvaluation] = useState<EvaluationResponse | null>(null);
  const [step, setStep] = useState<Step>("form");
  const [evalProgress, setEvalProgress] = useState(0);

  // Form state
  const [commitUrl, setCommitUrl] = useState("");
  const [approachNote, setApproachNote] = useState("");
  const [selfStatus, setSelfStatus] = useState("solved");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      const [t, subs] = await Promise.all([getTask(taskId), getMySubmissions(taskId)]);
      setTask(t);
      if (subs.length > 0) {
        setExistingSubmission(subs[0]);
        // Try to load existing evaluation
        try {
          const ev = await import("@/lib/api").then(m => m.getSubmissionEvaluation(subs[0].id));
          setEvaluation(ev);
          setStep("result");
        } catch {}
      }
    })();
  }, [taskId]);

  async function handleSubmit() {
    if (!commitUrl.trim()) { setError("Commit URL is required"); return; }
    setError(null);
    setSubmitting(true);
    try {
      const profile = await getMyStudentProfile();
      let sub = existingSubmission;
      if (!sub) {
        sub = await createSubmission({
          organization_id: profile.organization_id,
          task_id: taskId,
          student_id: profile.id,
          self_status: selfStatus,
          commit_url: commitUrl.trim(),
          approach_note: approachNote.trim() || undefined,
        });
        setExistingSubmission(sub);
      }

      // Start evaluation animation
      setStep("evaluating");
      const interval = setInterval(() => {
        setEvalProgress((p) => Math.min(p + 1, EVAL_STEPS.length - 1));
      }, 600);

      const ev = await triggerEvaluation(sub.id, false);
      clearInterval(interval);
      setEvalProgress(EVAL_STEPS.length);
      setEvaluation(ev);

      setTimeout(() => setStep("result"), 500);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Submission failed");
      setStep("form");
    } finally {
      setSubmitting(false);
    }
  }

  if (!task) return (
    <div className="flex items-center justify-center h-64">
      <div className="inline-block w-8 h-8 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin" />
    </div>
  );

  return (
    <div className="max-w-2xl space-y-6">
      <nav className="flex items-center gap-2 text-sm text-slate-500">
        <Link href="/student">Dashboard</Link>
        <span>›</span>
        <Link href={`/student/task/${taskId}`}>{task.title}</Link>
        <span>›</span>
        <span className="text-slate-700">Submit</span>
      </nav>

      {step === "form" && (
        <div className="space-y-4">
          <div className="bg-white rounded-xl border border-slate-200 p-5">
            <h1 className="font-bold text-slate-900 mb-1">{task.title}</h1>
            <p className="text-sm text-slate-500">Submit your GitHub commit for AI evaluation.</p>
          </div>

          <div className="bg-white rounded-xl border border-slate-200 p-5 space-y-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1.5">
                GitHub Commit URL <span className="text-red-500">*</span>
              </label>
              <input
                type="url"
                value={commitUrl}
                onChange={(e) => setCommitUrl(e.target.value)}
                placeholder="https://github.com/you/repo/commit/abc123"
                className="w-full rounded-lg border border-slate-200 px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1.5">Your Approach</label>
              <textarea
                value={approachNote}
                onChange={(e) => setApproachNote(e.target.value)}
                rows={3}
                placeholder="Briefly describe your implementation approach…"
                className="w-full rounded-lg border border-slate-200 px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 resize-none"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1.5">Self Assessment</label>
              <select
                value={selfStatus}
                onChange={(e) => setSelfStatus(e.target.value)}
                className="w-full rounded-lg border border-slate-200 px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 bg-white"
              >
                <option value="solved">Solved — I completed all requirements</option>
                <option value="partially_solved">Partially Solved — some requirements missing</option>
                <option value="attempted">Attempted — I gave it my best shot</option>
              </select>
            </div>

            {error && (
              <div className="rounded-lg bg-red-50 border border-red-200 px-3 py-2.5">
                <p className="text-sm text-red-700">{error}</p>
              </div>
            )}

            <button
              onClick={handleSubmit}
              disabled={submitting}
              className="w-full rounded-lg bg-indigo-600 py-2.5 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-60 transition-colors"
            >
              {submitting ? "Submitting…" : "Submit for AI Evaluation"}
            </button>
          </div>
        </div>
      )}

      {step === "evaluating" && (
        <div className="bg-white rounded-xl border border-slate-200 p-8 text-center">
          <div className="inline-block w-10 h-10 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin mb-4" />
          <h2 className="text-lg font-semibold text-slate-900 mb-6">Analysing Submission…</h2>
          <div className="space-y-3 text-left max-w-xs mx-auto">
            {EVAL_STEPS.map((s, i) => (
              <div key={i} className="flex items-center gap-3">
                {i < evalProgress ? (
                  <svg className="w-4 h-4 text-emerald-500 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
                  </svg>
                ) : i === evalProgress ? (
                  <div className="w-4 h-4 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin shrink-0" />
                ) : (
                  <div className="w-4 h-4 rounded-full border-2 border-slate-200 shrink-0" />
                )}
                <span className={`text-sm ${i <= evalProgress ? "text-slate-800" : "text-slate-400"}`}>{s}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {step === "result" && evaluation && (
        <EvaluationResultView evaluation={evaluation} task={task} />
      )}
    </div>
  );
}

function EvaluationResultView({ evaluation, task }: { evaluation: EvaluationResponse; task: Task }) {
  const result = evaluation.result;

  if (evaluation.state === "failed") return (
    <div className="rounded-xl bg-red-50 border border-red-200 p-6">
      <h2 className="font-semibold text-red-800 mb-1">Evaluation Failed</h2>
      <p className="text-sm text-red-700">{evaluation.error ?? "An error occurred during evaluation."}</p>
    </div>
  );

  if (!result) return (
    <div className="rounded-xl bg-amber-50 border border-amber-200 p-6">
      <p className="text-sm text-amber-700">Evaluation is {evaluation.state}. Please check back shortly.</p>
    </div>
  );

  return (
    <div className="space-y-4">
      {/* Score header */}
      <div className="bg-white rounded-xl border border-slate-200 p-6">
        <div className="flex items-center justify-between flex-wrap gap-4">
          <div>
            <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-1">AI Evaluation</p>
            <div className="flex items-center gap-3">
              <ScoreBadge score={result.overall_score} />
              <div>
                <StatusChip status={result.status} />
                <p className="mt-1 text-xs text-slate-500">Confidence: {(result.confidence * 100).toFixed(0)}%</p>
                <p className="text-xs text-slate-400">
                  {evaluation.mock_mode ? "Mock AI" : evaluation.provider} · {evaluation.model}
                </p>
              </div>
            </div>
          </div>
          {evaluation.state === "needs_human_review" && (
            <div className="rounded-lg bg-amber-50 border border-amber-200 px-3 py-2">
              <p className="text-xs font-medium text-amber-700">⚠ Pending mentor review</p>
            </div>
          )}
        </div>
        {result.summary && (
          <p className="mt-4 text-sm text-slate-600 border-t border-slate-100 pt-4">{result.summary}</p>
        )}
      </div>

      {/* Dimensions */}
      <div className="bg-white rounded-xl border border-slate-200 p-6">
        <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wide mb-4">Dimension Scores</h2>
        <div className="space-y-4">
          {Object.entries(result.dimensions).map(([key, dim]) => (
            <DimensionBar key={key} name={key} score={dim.score} reason={dim.reason} />
          ))}
        </div>
      </div>

      {/* Acceptance criteria */}
      {result.acceptance_criteria_results.length > 0 && (
        <div className="bg-white rounded-xl border border-slate-200 p-6">
          <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wide mb-3">Acceptance Criteria</h2>
          <div className="space-y-2">
            {result.acceptance_criteria_results.map((cr, i) => (
              <div key={i} className="flex items-start gap-3 py-2 border-b border-slate-50 last:border-0">
                <CriterionIcon status={cr.status} />
                <div>
                  <p className="text-sm text-slate-800">{cr.criterion}</p>
                  {cr.notes && <p className="text-xs text-slate-500 mt-0.5">{cr.notes}</p>}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Issues + Evidence */}
      {result.issues.length > 0 && (
        <div className="bg-white rounded-xl border border-slate-200 p-6">
          <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wide mb-3">Issues Found</h2>
          <div className="space-y-2">
            {result.issues.map((item, i) => <EvidenceCard key={i} item={item} />)}
          </div>
        </div>
      )}

      {/* Strengths */}
      {result.strengths.length > 0 && (
        <div className="bg-white rounded-xl border border-slate-200 p-6">
          <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wide mb-3">What You Did Well</h2>
          <ul className="space-y-1.5">
            {result.strengths.map((s, i) => (
              <li key={i} className="flex items-start gap-2 text-sm text-slate-700">
                <span className="mt-0.5 text-emerald-500 font-bold">✓</span>
                {s}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Missing requirements */}
      {result.missing_requirements.length > 0 && (
        <div className="bg-white rounded-xl border border-slate-200 p-6">
          <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wide mb-3">Missing Requirements</h2>
          <ul className="space-y-1.5">
            {result.missing_requirements.map((r, i) => (
              <li key={i} className="flex items-start gap-2 text-sm text-red-700">
                <span className="mt-0.5">✗</span>
                {r}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Mentor review */}
      {evaluation.mentor_decision && (
        <div className="bg-white rounded-xl border border-slate-200 p-6">
          <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wide mb-2">Mentor Review</h2>
          <StatusChip status={evaluation.mentor_decision} />
          {evaluation.mentor_feedback && (
            <p className="mt-2 text-sm text-slate-700 italic">"{evaluation.mentor_feedback}"</p>
          )}
        </div>
      )}
    </div>
  );
}

function CriterionIcon({ status }: { status: string }) {
  if (status === "PASS") return (
    <svg className="w-4 h-4 mt-0.5 text-emerald-500 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
    </svg>
  );
  if (status === "FAIL") return (
    <svg className="w-4 h-4 mt-0.5 text-red-500 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
    </svg>
  );
  if (status === "PARTIAL") return <span className="text-amber-500 font-bold mt-0.5 text-xs shrink-0">½</span>;
  return <span className="text-slate-400 font-bold mt-0.5 text-xs shrink-0">?</span>;
}
