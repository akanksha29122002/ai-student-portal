"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { getMyStudentProfile, getTodayTask, getLearningPlan, generateLearningPlan } from "@/lib/api";
import { Student, LearningPlanDay, Task, LearningPlan } from "@/lib/types";

type TodayData = { day: LearningPlanDay | null; task: Task | null };

function StatusBadge({ status }: { status: LearningPlanDay["status"] }) {
  const map: Record<string, { label: string; cls: string }> = {
    locked: { label: "Locked", cls: "bg-slate-100 text-slate-500" },
    available: { label: "Available", cls: "bg-blue-100 text-blue-700" },
    in_progress: { label: "In Progress", cls: "bg-amber-100 text-amber-700" },
    completed: { label: "Completed", cls: "bg-green-100 text-green-700" },
    skipped: { label: "Skipped", cls: "bg-slate-100 text-slate-500" },
    blocked: { label: "Blocked", cls: "bg-red-100 text-red-700" },
  };
  const { label, cls } = map[status] ?? { label: status, cls: "bg-slate-100 text-slate-600" };
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${cls}`}>
      {label}
    </span>
  );
}

export default function TodayPage() {
  const [student, setStudent] = useState<Student | null>(null);
  const [data, setData] = useState<TodayData | null>(null);
  const [plan, setPlan] = useState<{ plan: LearningPlan; days: LearningPlanDay[] } | null>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const s = await getMyStudentProfile();
        setStudent(s);
        const [today, p] = await Promise.allSettled([getTodayTask(s.id), getLearningPlan(s.id)]);
        if (today.status === "fulfilled") setData(today.value);
        if (p.status === "fulfilled") setPlan(p.value);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const handleGeneratePlan = async () => {
    if (!student) return;
    setGenerating(true);
    try {
      const p = await generateLearningPlan(student.id);
      setPlan(p);
      const today = await getTodayTask(student.id);
      setData(today);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to generate plan");
    } finally {
      setGenerating(false);
    }
  };

  if (loading) return (
    <div className="flex items-center justify-center h-64">
      <div className="inline-block w-8 h-8 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin" />
    </div>
  );

  if (error) return (
    <div className="rounded-xl bg-red-50 border border-red-200 p-4">
      <p className="text-sm text-red-700">{error}</p>
    </div>
  );

  const todayDate = new Date().toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric" });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Today</h1>
        <p className="mt-1 text-sm text-slate-500">{todayDate}</p>
      </div>

      {!plan && (
        <div className="bg-indigo-50 border border-indigo-200 rounded-xl p-6 text-center">
          <p className="text-slate-700 mb-3">You don't have an active 14-day learning plan yet.</p>
          <button
            onClick={handleGeneratePlan}
            disabled={generating}
            className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-50 transition-colors"
          >
            {generating ? "Generating…" : "Generate My 14-Day Plan"}
          </button>
        </div>
      )}

      {data?.day ? (
        <div className="space-y-4">
          <div className="bg-white rounded-xl border border-slate-200 p-5">
            <div className="flex items-center justify-between mb-3">
              <h2 className="font-semibold text-slate-900">Day {data.day.day_number}</h2>
              <StatusBadge status={data.day.status} />
            </div>
            {data.day.target_skills.length > 0 && (
              <div className="flex flex-wrap gap-1.5 mb-3">
                {data.day.target_skills.map((s) => (
                  <span key={s} className="rounded-full bg-indigo-50 text-indigo-700 text-xs px-2 py-0.5 font-medium">
                    {s.replace(/_/g, " ")}
                  </span>
                ))}
              </div>
            )}
            {data.day.score !== null && (
              <p className="text-sm text-slate-600">Score: <span className="font-semibold text-indigo-600">{data.day.score}/100</span></p>
            )}
          </div>

          {data.task ? (
            <div className="bg-white rounded-xl border border-slate-200 p-5">
              <h3 className="font-semibold text-slate-900 mb-1">{data.task.title}</h3>
              <p className="text-sm text-slate-600 mb-4 line-clamp-3">{data.task.problem_statement}</p>
              <div className="flex gap-3">
                <Link
                  href={`/student/task/${data.task.id}`}
                  className="rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-50"
                >
                  View Task
                </Link>
                <Link
                  href={`/student/submit/${data.task.id}`}
                  className="rounded-lg bg-indigo-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-indigo-700"
                >
                  Submit
                </Link>
              </div>
            </div>
          ) : (
            <div className="bg-slate-50 rounded-xl border border-slate-200 p-5 text-center">
              <p className="text-sm text-slate-500">No task assigned to this day yet. The mentor will assign one shortly.</p>
            </div>
          )}
        </div>
      ) : plan ? (
        <div className="bg-white rounded-xl border border-slate-200 p-6 text-center">
          <p className="text-slate-600">No task scheduled for today in your plan.</p>
          <Link href="/student/plan" className="mt-2 inline-block text-sm text-indigo-600 hover:underline">View full plan →</Link>
        </div>
      ) : null}

      <div className="flex justify-end">
        <Link href="/student/plan" className="text-sm text-indigo-600 hover:underline">View full 14-day plan →</Link>
      </div>
    </div>
  );
}
