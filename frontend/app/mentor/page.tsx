"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { listStudents, getStudentTasks, getStudentSubmissions, getSubmissionEvaluation } from "@/lib/api";
import { Student, Task, Submission, EvaluationResponse } from "@/lib/types";
import { ScoreBadge } from "@/components/ScoreBadge";
import { StatusChip } from "@/components/StatusChip";

interface StudentRow {
  student: Student;
  task: Task | null;
  submission: Submission | null;
  evaluation: EvaluationResponse | null;
}

export default function MentorDashboard() {
  const [rows, setRows] = useState<StudentRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const students = await listStudents();
        const rowData = await Promise.all(
          students.map(async (student): Promise<StudentRow> => {
            try {
              const tasks = await getStudentTasks(student.id);
              const task = tasks[0] ?? null;
              const subs = task ? await getStudentSubmissions(student.id) : [];
              const sub = subs.find((s) => s.task_id === task?.id) ?? null;
              let evaluation: EvaluationResponse | null = null;
              if (sub) {
                try { evaluation = await getSubmissionEvaluation(sub.id); } catch {}
              }
              return { student, task, submission: sub, evaluation };
            } catch {
              return { student, task: null, submission: null, evaluation: null };
            }
          })
        );
        setRows(rowData);
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : "Failed to load dashboard");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const total = rows.length;
  const submitted = rows.filter((r) => r.submission).length;
  const needsReview = rows.filter((r) => r.evaluation?.state === "needs_human_review").length;
  const avgScore = (() => {
    const scores = rows.filter((r) => r.evaluation?.result?.overall_score != null)
      .map((r) => r.evaluation!.result!.overall_score);
    return scores.length ? scores.reduce((a, b) => a + b, 0) / scores.length : null;
  })();

  if (loading) return (
    <div className="flex items-center justify-center h-64">
      <div className="text-center">
        <div className="inline-block w-8 h-8 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin mb-3" />
        <p className="text-sm text-slate-500">Loading dashboard…</p>
      </div>
    </div>
  );

  if (error) return (
    <div className="rounded-xl bg-red-50 border border-red-200 p-4">
      <p className="text-sm text-red-700">{error}</p>
    </div>
  );

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Mentor Dashboard</h1>
          <p className="text-sm text-slate-500 mt-0.5">Today's defense status</p>
        </div>
        <Link
          href="/mentor/evaluations"
          className="rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-50 transition-colors"
        >
          All Evaluations →
        </Link>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        {[
          { label: "Total Students", value: total, sub: null, color: "text-slate-800" },
          { label: "Submitted Today", value: submitted, sub: `${total - submitted} pending`, color: "text-indigo-600" },
          { label: "Needs Review", value: needsReview, sub: "AI flagged", color: needsReview > 0 ? "text-amber-600" : "text-slate-400" },
          { label: "Average Score", value: avgScore !== null ? avgScore.toFixed(1) : "—", sub: "out of 10", color: avgScore !== null && avgScore >= 7 ? "text-emerald-600" : "text-amber-600" },
        ].map((stat) => (
          <div key={stat.label} className="bg-white rounded-xl border border-slate-200 p-4">
            <p className="text-xs text-slate-400 font-medium">{stat.label}</p>
            <p className={`text-3xl font-bold mt-1 tabular-nums ${stat.color}`}>{stat.value}</p>
            {stat.sub && <p className="text-xs text-slate-400 mt-0.5">{stat.sub}</p>}
          </div>
        ))}
      </div>

      {/* Needs attention */}
      {needsReview > 0 && (
        <div>
          <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wide mb-3">
            Requires Attention ({needsReview})
          </h2>
          <div className="grid gap-3 sm:grid-cols-2">
            {rows.filter((r) => r.evaluation?.state === "needs_human_review").map(({ student, task, evaluation }) => (
              <div key={student.id} className="bg-white rounded-xl border border-amber-200 p-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="font-semibold text-slate-900">{student.full_name}</p>
                    <p className="text-xs text-slate-500 mt-0.5 truncate">{task?.title}</p>
                    {evaluation?.result?.mentor_attention_reasons?.length ? (
                      <p className="text-xs text-amber-700 mt-1.5">
                        {evaluation.result.mentor_attention_reasons[0]}
                      </p>
                    ) : null}
                  </div>
                  {evaluation?.result && (
                    <ScoreBadge score={evaluation.result.overall_score} size="sm" />
                  )}
                </div>
                {evaluation && (
                  <Link
                    href={`/mentor/evaluations/${evaluation.evaluation_id}`}
                    className="mt-3 block w-full text-center rounded-lg bg-amber-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-amber-700 transition-colors"
                  >
                    Review Evaluation
                  </Link>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Student table */}
      <div>
        <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wide mb-3">All Students</h2>
        <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-100">
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase tracking-wide">Student</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase tracking-wide hidden sm:table-cell">Task</th>
                <th className="text-right px-4 py-3 text-xs font-semibold text-slate-400 uppercase tracking-wide">Score</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase tracking-wide hidden md:table-cell">AI Status</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase tracking-wide">Review</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody>
              {rows.map(({ student, task, submission, evaluation }, i) => (
                <tr key={student.id} className={`border-b border-slate-50 last:border-0 hover:bg-slate-50 transition-colors ${i % 2 === 0 ? "" : "bg-slate-50/30"}`}>
                  <td className="px-4 py-3">
                    <Link href={`/mentor/students/${student.id}`} className="font-medium text-slate-800 hover:text-indigo-600">{student.full_name}</Link>
                    <div className="text-xs text-slate-400">{student.email}</div>
                  </td>
                  <td className="px-4 py-3 hidden sm:table-cell">
                    <span className="text-slate-600 line-clamp-1 max-w-[180px]">{task?.title ?? "—"}</span>
                  </td>
                  <td className="px-4 py-3 text-right">
                    {evaluation?.result ? (
                      <ScoreBadge score={evaluation.result.overall_score} size="sm" />
                    ) : (
                      <span className="text-slate-400">—</span>
                    )}
                  </td>
                  <td className="px-4 py-3 hidden md:table-cell">
                    {evaluation ? (
                      <StatusChip status={evaluation.state} />
                    ) : submission ? (
                      <StatusChip status="pending" />
                    ) : (
                      <span className="text-xs text-slate-400">No submission</span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    {evaluation ? (
                      <StatusChip status={evaluation.mentor_decision ?? "pending"} />
                    ) : (
                      <span className="text-xs text-slate-400">—</span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    {evaluation && (
                      <Link
                        href={`/mentor/evaluations/${evaluation.evaluation_id}`}
                        className="rounded-lg border border-slate-200 px-2.5 py-1 text-xs font-medium text-slate-600 hover:bg-slate-100 transition-colors whitespace-nowrap"
                      >
                        View →
                      </Link>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
