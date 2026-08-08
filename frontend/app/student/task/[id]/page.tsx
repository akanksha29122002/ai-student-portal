"use client";
import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { getTask } from "@/lib/api";
import { Task } from "@/lib/types";

export default function TaskPage() {
  const { id } = useParams<{ id: string }>();
  const [task, setTask] = useState<Task | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getTask(id).then(setTask).catch((e) => setError(e.message)).finally(() => setLoading(false));
  }, [id]);

  if (loading) return <LoadingState />;
  if (error || !task) return <ErrorState msg={error ?? "Task not found"} />;

  return (
    <div className="max-w-2xl space-y-6">
      {/* Breadcrumb */}
      <nav className="flex items-center gap-2 text-sm text-slate-500">
        <Link href="/student" className="hover:text-slate-700">Dashboard</Link>
        <span>›</span>
        <span className="text-slate-700">Task</span>
      </nav>

      {/* Header */}
      <div className="bg-white rounded-xl border border-slate-200 p-6">
        <div className="flex items-start justify-between gap-4">
          <div>
            <span className="inline-flex items-center rounded-full bg-indigo-50 border border-indigo-200 px-2.5 py-0.5 text-xs font-medium text-indigo-700 mb-3">
              {task.task_type === "coding" ? "Coding Task" : "Spoken Question"}
            </span>
            <h1 className="text-xl font-bold text-slate-900">{task.title}</h1>
            <p className="mt-1 text-sm text-slate-500">
              Due: {new Date(task.due_on).toLocaleDateString("en-IN", { weekday: "long", day: "numeric", month: "long" })}
            </p>
          </div>
        </div>
      </div>

      {/* Problem Statement */}
      <section className="bg-white rounded-xl border border-slate-200 p-6">
        <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wide mb-3">Problem Statement</h2>
        <p className="text-slate-700 leading-relaxed text-sm">{task.problem_statement}</p>
      </section>

      {/* Acceptance Criteria */}
      <section className="bg-white rounded-xl border border-slate-200 p-6">
        <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wide mb-3">Acceptance Criteria</h2>
        <ul className="space-y-2">
          {task.acceptance_criteria.map((c, i) => (
            <li key={i} className="flex items-start gap-3">
              <span className="mt-0.5 flex-shrink-0 w-5 h-5 rounded-full border-2 border-slate-300 flex items-center justify-center">
                <span className="text-xs text-slate-400">{i + 1}</span>
              </span>
              <span className="text-sm text-slate-700">{c}</span>
            </li>
          ))}
        </ul>
      </section>

      {/* Expected Concepts */}
      {task.expected_concepts.length > 0 && (
        <section className="bg-white rounded-xl border border-slate-200 p-6">
          <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wide mb-3">Expected Concepts</h2>
          <div className="flex flex-wrap gap-2">
            {task.expected_concepts.map((c) => (
              <span key={c} className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-600">
                {c}
              </span>
            ))}
          </div>
        </section>
      )}

      {/* CTA */}
      <Link
        href={`/student/submit/${task.id}`}
        className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-5 py-2.5 text-sm font-semibold text-white hover:bg-indigo-700 transition-colors"
      >
        Submit Work
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" />
        </svg>
      </Link>
    </div>
  );
}

function LoadingState() {
  return (
    <div className="flex items-center justify-center h-64">
      <div className="text-center">
        <div className="inline-block w-8 h-8 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin mb-3" />
        <p className="text-sm text-slate-500">Loading task…</p>
      </div>
    </div>
  );
}

function ErrorState({ msg }: { msg: string }) {
  return (
    <div className="rounded-xl bg-red-50 border border-red-200 p-4">
      <p className="text-sm text-red-700">{msg}</p>
    </div>
  );
}
