"use client";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { getEvaluation, submitMentorReview } from "@/lib/api";
import { EvaluationResponse, MentorDecision } from "@/lib/types";
import { ScoreBadge } from "@/components/ScoreBadge";
import { StatusChip } from "@/components/StatusChip";
import { DimensionBar } from "@/components/DimensionBar";
import { EvidenceCard } from "@/components/EvidenceCard";

const DECISIONS: { value: MentorDecision; label: string; color: string }[] = [
  { value: "APPROVED", label: "Approve", color: "bg-emerald-600 hover:bg-emerald-700 text-white" },
  { value: "REQUEST_CHANGES", label: "Request Changes", color: "bg-amber-600 hover:bg-amber-700 text-white" },
  { value: "REJECTED", label: "Reject", color: "bg-red-600 hover:bg-red-700 text-white" },
  { value: "OVERRIDE_SCORE", label: "Override Score", color: "bg-indigo-600 hover:bg-indigo-700 text-white" },
];

export default function MentorEvaluationPage() {
  const { id } = useParams<{ id: string }>();
  const [evaluation, setEvaluation] = useState<EvaluationResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Review form state
  const [decision, setDecision] = useState<MentorDecision>("APPROVED");
  const [feedback, setFeedback] = useState("");
  const [overrideScore, setOverrideScore] = useState<string>("");
  const [submitting, setSubmitting] = useState(false);
  const [reviewError, setReviewError] = useState<string | null>(null);
  const [reviewDone, setReviewDone] = useState(false);

  useEffect(() => {
    getEvaluation(id)
      .then((ev) => { setEvaluation(ev); if (ev.mentor_decision) setReviewDone(true); })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [id]);

  async function handleReview() {
    if (!feedback.trim()) { setReviewError("Feedback is required"); return; }
    setReviewError(null);
    setSubmitting(true);
    try {
      const override = decision === "OVERRIDE_SCORE" && overrideScore ? parseFloat(overrideScore) : undefined;
      const updated = await submitMentorReview(id, decision, feedback, override);
      setEvaluation(updated);
      setReviewDone(true);
    } catch (e: unknown) {
      setReviewError(e instanceof Error ? e.message : "Review submission failed");
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) return (
    <div className="flex items-center justify-center h-64">
      <div className="w-8 h-8 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin" />
    </div>
  );
  if (error || !evaluation) return (
    <div className="rounded-xl bg-red-50 border border-red-200 p-4">
      <p className="text-sm text-red-700">{error ?? "Evaluation not found"}</p>
    </div>
  );

  const result = evaluation.result;

  return (
    <div className="max-w-3xl space-y-5">
      {/* Breadcrumb */}
      <nav className="flex items-center gap-2 text-sm text-slate-500">
        <Link href="/mentor" className="hover:text-slate-700">Dashboard</Link>
        <span>›</span>
        <Link href="/mentor/evaluations" className="hover:text-slate-700">Evaluations</Link>
        <span>›</span>
        <span className="text-slate-700 font-mono text-xs">{id.slice(0, 8)}…</span>
      </nav>

      {/* Score summary */}
      <div className="bg-white rounded-xl border border-slate-200 p-6">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-2">AI Evaluation</p>
            <div className="flex items-center gap-4">
              {result && <ScoreBadge score={result.overall_score} />}
              <div className="space-y-1">
                <StatusChip status={evaluation.state} />
                {result && <StatusChip status={result.status} />}
                <p className="text-xs text-slate-400">
                  Confidence: {result ? (result.confidence * 100).toFixed(0) + "%" : "—"}
                </p>
                <p className="text-xs text-slate-400">
                  {evaluation.mock_mode ? "Mock AI" : evaluation.provider} · {evaluation.model}
                  {" "}· {evaluation.duration_ms}ms · {evaluation.input_tokens}+{evaluation.output_tokens} tokens
                </p>
              </div>
            </div>
          </div>
          {evaluation.mentor_decision && (
            <div className="space-y-1">
              <p className="text-xs text-slate-400 font-medium">Mentor Decision</p>
              <StatusChip status={evaluation.mentor_decision} />
            </div>
          )}
        </div>

        {result?.summary && (
          <p className="mt-4 text-sm text-slate-600 border-t border-slate-100 pt-4 leading-relaxed">
            {result.summary}
          </p>
        )}
      </div>

      {/* Acceptance criteria */}
      {result?.acceptance_criteria_results?.length ? (
        <div className="bg-white rounded-xl border border-slate-200 p-6">
          <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wide mb-3">Acceptance Criteria</h2>
          <div className="space-y-2">
            {result.acceptance_criteria_results.map((cr, i) => (
              <div key={i} className="flex items-start gap-3 py-2 border-b border-slate-50 last:border-0">
                <CritIcon status={cr.status} />
                <div>
                  <p className="text-sm text-slate-800">{cr.criterion}</p>
                  {cr.notes && <p className="text-xs text-slate-500 mt-0.5">{cr.notes}</p>}
                </div>
                <span className={`ml-auto shrink-0 text-xs font-medium px-2 py-0.5 rounded-full ${
                  cr.status === "PASS" ? "bg-emerald-50 text-emerald-700" :
                  cr.status === "FAIL" ? "bg-red-50 text-red-700" :
                  cr.status === "PARTIAL" ? "bg-amber-50 text-amber-700" :
                  "bg-slate-100 text-slate-500"
                }`}>{cr.status}</span>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      {/* Dimension scores */}
      {result && (
        <div className="bg-white rounded-xl border border-slate-200 p-6">
          <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wide mb-4">Dimension Scores</h2>
          <div className="space-y-4">
            {Object.entries(result.dimensions).map(([key, dim]) => (
              <DimensionBar key={key} name={key} score={dim.score} reason={dim.reason} />
            ))}
          </div>
        </div>
      )}

      {/* Issues + Evidence */}
      {result?.issues?.length ? (
        <div className="bg-white rounded-xl border border-slate-200 p-6">
          <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wide mb-3">Issues Found</h2>
          <div className="space-y-2">
            {result.issues.map((item, i) => <EvidenceCard key={i} item={item} />)}
          </div>
        </div>
      ) : null}

      {/* Security concerns */}
      {result?.security_concerns?.length ? (
        <div className="bg-white rounded-xl border border-red-100 p-6">
          <h2 className="text-sm font-semibold text-red-600 uppercase tracking-wide mb-3">Security Concerns</h2>
          <div className="space-y-2">
            {result.security_concerns.map((item, i) => <EvidenceCard key={i} item={item} />)}
          </div>
        </div>
      ) : null}

      {/* Strengths */}
      {result?.strengths?.length ? (
        <div className="bg-white rounded-xl border border-slate-200 p-6">
          <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wide mb-2">Strengths</h2>
          <ul className="space-y-1.5">
            {result.strengths.map((s, i) => (
              <li key={i} className="flex items-start gap-2 text-sm text-slate-700">
                <span className="text-emerald-500 font-bold mt-0.5">✓</span>
                {s}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {/* Missing requirements */}
      {result?.missing_requirements?.length ? (
        <div className="bg-white rounded-xl border border-slate-200 p-6">
          <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wide mb-2">Missing Requirements</h2>
          <ul className="space-y-1.5">
            {result.missing_requirements.map((r, i) => (
              <li key={i} className="flex items-start gap-2 text-sm text-red-700">
                <span className="mt-0.5">✗</span>{r}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {/* Suggested improvements */}
      {result?.suggested_improvements?.length ? (
        <div className="bg-white rounded-xl border border-slate-200 p-6">
          <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wide mb-2">Suggested Improvements</h2>
          <ul className="space-y-1.5 list-disc list-inside">
            {result.suggested_improvements.map((s, i) => (
              <li key={i} className="text-sm text-slate-600">{s}</li>
            ))}
          </ul>
        </div>
      ) : null}

      {/* Mentor review form */}
      <div className="bg-white rounded-xl border border-slate-200 p-6">
        <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wide mb-4">Mentor Review</h2>

        {reviewDone ? (
          <div className="space-y-3">
            <div className="flex items-center gap-2 rounded-lg bg-emerald-50 border border-emerald-200 px-4 py-3">
              <svg className="w-4 h-4 text-emerald-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
              </svg>
              <p className="text-sm font-medium text-emerald-800">Mentor Review Completed</p>
            </div>
            {evaluation.mentor_decision && <StatusChip status={evaluation.mentor_decision} />}
            {evaluation.mentor_feedback && (
              <p className="text-sm text-slate-600 italic">"{evaluation.mentor_feedback}"</p>
            )}
            <button
              onClick={() => setReviewDone(false)}
              className="text-xs text-slate-400 hover:text-slate-600 underline"
            >
              Update review
            </button>
          </div>
        ) : (
          <div className="space-y-4">
            {/* Decision buttons */}
            <div>
              <p className="text-sm font-medium text-slate-700 mb-2">Decision</p>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                {DECISIONS.map((d) => (
                  <button
                    key={d.value}
                    onClick={() => setDecision(d.value)}
                    className={`rounded-lg px-3 py-2 text-sm font-medium transition-all border ${
                      decision === d.value
                        ? `${d.color} border-transparent shadow-sm`
                        : "bg-white text-slate-600 border-slate-200 hover:border-slate-300"
                    }`}
                  >
                    {d.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Override score */}
            {decision === "OVERRIDE_SCORE" && (
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1.5">
                  Override Score (0–10)
                </label>
                <input
                  type="number"
                  min="0"
                  max="10"
                  step="0.1"
                  value={overrideScore}
                  onChange={(e) => setOverrideScore(e.target.value)}
                  className="w-32 rounded-lg border border-slate-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>
            )}

            {/* Feedback */}
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1.5">
                Feedback <span className="text-red-500">*</span>
              </label>
              <textarea
                value={feedback}
                onChange={(e) => setFeedback(e.target.value)}
                rows={4}
                placeholder="Provide specific, actionable feedback to the student…"
                className="w-full rounded-lg border border-slate-200 px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 resize-none"
              />
            </div>

            {reviewError && (
              <div className="rounded-lg bg-red-50 border border-red-200 px-3 py-2.5">
                <p className="text-sm text-red-700">{reviewError}</p>
              </div>
            )}

            <button
              onClick={handleReview}
              disabled={submitting}
              className="rounded-lg bg-indigo-600 px-5 py-2.5 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-60 transition-colors"
            >
              {submitting ? "Submitting…" : "Submit Review"}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

function CritIcon({ status }: { status: string }) {
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
  return <span className="text-amber-500 mt-0.5 shrink-0 text-sm">~</span>;
}
