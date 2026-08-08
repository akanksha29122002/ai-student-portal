"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { listEvaluations } from "@/lib/api";
import { EvaluationResponse } from "@/lib/types";
import { ScoreBadge } from "@/components/ScoreBadge";
import { StatusChip } from "@/components/StatusChip";

export default function EvaluationsListPage() {
  const [evals, setEvals] = useState<EvaluationResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [needsReviewOnly, setNeedsReviewOnly] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    listEvaluations(needsReviewOnly, 100)
      .then(setEvals)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [needsReviewOnly]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Evaluations</h1>
          <p className="text-sm text-slate-500 mt-0.5">{evals.length} evaluations</p>
        </div>
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={needsReviewOnly}
            onChange={(e) => setNeedsReviewOnly(e.target.checked)}
            className="w-4 h-4 text-indigo-600 rounded border-slate-300"
          />
          <span className="text-sm font-medium text-slate-600">Needs review only</span>
        </label>
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-40">
          <div className="w-7 h-7 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin" />
        </div>
      ) : error ? (
        <div className="rounded-xl bg-red-50 border border-red-200 p-4">
          <p className="text-sm text-red-700">{error}</p>
        </div>
      ) : evals.length === 0 ? (
        <div className="bg-white rounded-xl border border-slate-200 p-12 text-center">
          <p className="text-slate-400">No evaluations found.</p>
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-100">
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase tracking-wide">Evaluation ID</th>
                <th className="text-right px-4 py-3 text-xs font-semibold text-slate-400 uppercase tracking-wide">Score</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase tracking-wide hidden sm:table-cell">State</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase tracking-wide hidden md:table-cell">Provider</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase tracking-wide">Mentor</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody>
              {evals.map((ev) => (
                <tr key={ev.evaluation_id} className="border-b border-slate-50 last:border-0 hover:bg-slate-50 transition-colors">
                  <td className="px-4 py-3 font-mono text-xs text-slate-500">
                    {ev.evaluation_id.slice(0, 8)}…
                  </td>
                  <td className="px-4 py-3 text-right">
                    {ev.result ? (
                      <ScoreBadge score={ev.result.overall_score} size="sm" />
                    ) : "—"}
                  </td>
                  <td className="px-4 py-3 hidden sm:table-cell">
                    <StatusChip status={ev.state} />
                  </td>
                  <td className="px-4 py-3 hidden md:table-cell text-slate-500">
                    {ev.mock_mode ? "Mock AI" : ev.provider}
                  </td>
                  <td className="px-4 py-3">
                    {ev.mentor_decision ? (
                      <StatusChip status={ev.mentor_decision} />
                    ) : (
                      <span className="text-xs text-slate-400">Pending</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <Link
                      href={`/mentor/evaluations/${ev.evaluation_id}`}
                      className="rounded-lg border border-slate-200 px-2.5 py-1 text-xs font-medium text-slate-600 hover:bg-slate-100 transition-colors"
                    >
                      Review →
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
