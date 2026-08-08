"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { getMyTasks, getMySubmissions } from "@/lib/api";
import { Task, Submission } from "@/lib/types";
import { getUser } from "@/lib/auth";
import { StatusChip } from "@/components/StatusChip";

function diffDays(dueOn: string) {
  const due = new Date(dueOn);
  const now = new Date();
  due.setHours(23, 59, 59, 0);
  const diff = Math.ceil((due.getTime() - now.getTime()) / 86400000);
  if (diff < 0) return { label: "Overdue", color: "text-red-600" };
  if (diff === 0) return { label: "Due today", color: "text-amber-600" };
  return { label: `Due in ${diff} day${diff !== 1 ? "s" : ""}`, color: "text-slate-500" };
}

export default function StudentDashboard() {
  const router = useRouter();
  const [tasks, setTasks] = useState<Task[]>([]);
  const [submissions, setSubmissions] = useState<Submission[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const user = getUser();

  useEffect(() => {
    (async () => {
      try {
        const [t, s] = await Promise.all([getMyTasks(), getMySubmissions()]);
        setTasks(t);
        setSubmissions(s);
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : "Failed to load dashboard");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const submissionByTask = Object.fromEntries(
    submissions.map((s) => [s.task_id, s])
  );

  if (loading) return (
    <div className="flex items-center justify-center h-64">
      <div className="text-center">
        <div className="inline-block w-8 h-8 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin mb-3" />
        <p className="text-sm text-slate-500">Loading your tasks…</p>
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
      <div>
        <h1 className="text-2xl font-bold text-slate-900">
          Good {getGreeting()}, {user?.full_name?.split(" ")[0] ?? "Student"}
        </h1>
        <p className="mt-1 text-slate-500 text-sm">Here are your assigned tasks.</p>
      </div>

      {/* Stats strip */}
      <div className="grid grid-cols-3 gap-4">
        {[
          { label: "Total Tasks", value: tasks.length, color: "text-slate-800" },
          { label: "Submitted", value: submissions.length, color: "text-indigo-600" },
          { label: "Pending", value: tasks.length - submissions.length, color: "text-amber-600" },
        ].map((s) => (
          <div key={s.label} className="bg-white rounded-xl border border-slate-200 p-4">
            <p className="text-xs text-slate-500 font-medium">{s.label}</p>
            <p className={`text-3xl font-bold mt-1 ${s.color}`}>{s.value}</p>
          </div>
        ))}
      </div>

      {/* Task list */}
      {tasks.length === 0 ? (
        <div className="bg-white rounded-xl border border-slate-200 p-12 text-center">
          <p className="text-slate-500">No tasks assigned yet.</p>
        </div>
      ) : (
        <div className="space-y-3">
          <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wide">Your Tasks</h2>
          {tasks.map((task) => {
            const sub = submissionByTask[task.id];
            const due = diffDays(task.due_on);
            return (
              <div key={task.id} className="bg-white rounded-xl border border-slate-200 p-5 hover:border-indigo-200 hover:shadow-sm transition-all">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <h3 className="font-semibold text-slate-900 truncate">{task.title}</h3>
                    <p className="mt-1 text-sm text-slate-500 line-clamp-2">{task.problem_statement}</p>
                    <div className="mt-2 flex items-center gap-3">
                      <span className={`text-xs font-medium ${due.color}`}>{due.label}</span>
                      {sub && <StatusChip status={sub.status} />}
                    </div>
                  </div>
                  <div className="flex gap-2 shrink-0">
                    <Link
                      href={`/student/task/${task.id}`}
                      className="rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-50 transition-colors"
                    >
                      View Task
                    </Link>
                    {!sub ? (
                      <Link
                        href={`/student/submit/${task.id}`}
                        className="rounded-lg bg-indigo-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-indigo-700 transition-colors"
                      >
                        Submit
                      </Link>
                    ) : (
                      <Link
                        href={`/student/submit/${task.id}`}
                        className="rounded-lg bg-slate-100 px-3 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-200 transition-colors"
                      >
                        View Result
                      </Link>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function getGreeting() {
  const h = new Date().getHours();
  if (h < 12) return "morning";
  if (h < 17) return "afternoon";
  return "evening";
}
