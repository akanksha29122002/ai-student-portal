"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { getMyStudentProfile, getLearningPlan, generateLearningPlan, getStudentSkills } from "@/lib/api";
import { LearningPlan, LearningPlanDay, SkillAssessment, Student } from "@/lib/types";

const STATUS_CONFIG: Record<string, { label: string; bg: string; text: string; dot: string }> = {
  locked:      { label: "Locked",      bg: "bg-slate-50",   text: "text-slate-400", dot: "bg-slate-300" },
  available:   { label: "Available",   bg: "bg-blue-50",    text: "text-blue-700",  dot: "bg-blue-400" },
  in_progress: { label: "In Progress", bg: "bg-amber-50",   text: "text-amber-700", dot: "bg-amber-400" },
  completed:   { label: "Completed",   bg: "bg-green-50",   text: "text-green-700", dot: "bg-green-500" },
  skipped:     { label: "Skipped",     bg: "bg-slate-50",   text: "text-slate-400", dot: "bg-slate-300" },
  blocked:     { label: "Blocked",     bg: "bg-red-50",     text: "text-red-700",   dot: "bg-red-400" },
};

function DayCard({ day }: { day: LearningPlanDay }) {
  const cfg = STATUS_CONFIG[day.status] ?? STATUS_CONFIG.locked;
  const isToday = day.scheduled_date === new Date().toISOString().split("T")[0];
  return (
    <div className={`rounded-xl border p-4 transition-all ${cfg.bg} ${isToday ? "ring-2 ring-indigo-400 ring-offset-1" : "border-slate-200"}`}>
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-semibold text-slate-500">Day {day.day_number}</span>
        <span className={`flex items-center gap-1 text-xs font-medium ${cfg.text}`}>
          <span className={`w-1.5 h-1.5 rounded-full ${cfg.dot}`} />
          {cfg.label}
        </span>
      </div>
      <p className="text-xs text-slate-500 mb-2">
        {new Date(day.scheduled_date).toLocaleDateString("en-US", { month: "short", day: "numeric" })}
        {isToday && <span className="ml-1 text-indigo-600 font-medium">· Today</span>}
      </p>
      {day.target_skills.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {day.target_skills.slice(0, 2).map((s) => (
            <span key={s} className="rounded-full bg-white/60 text-slate-600 text-[10px] px-1.5 py-0.5 border border-slate-200">
              {s.replace(/_/g, " ")}
            </span>
          ))}
        </div>
      )}
      {day.score !== null && (
        <p className={`mt-2 text-xs font-semibold ${cfg.text}`}>{day.score}/100</p>
      )}
    </div>
  );
}

function SkillBar({ dimension, score, confidence }: { dimension: string; score: number; confidence: string }) {
  const color = score >= 70 ? "bg-green-500" : score >= 40 ? "bg-amber-400" : "bg-red-400";
  return (
    <div>
      <div className="flex justify-between text-xs mb-1">
        <span className="text-slate-700 font-medium">{dimension.replace(/_/g, " ")}</span>
        <span className="text-slate-500">{score}<span className="text-slate-400">/100</span></span>
      </div>
      <div className="h-1.5 bg-slate-100 rounded-full overflow-hidden">
        <div className={`h-full ${color} rounded-full transition-all`} style={{ width: `${score}%` }} />
      </div>
      <p className="text-[10px] text-slate-400 mt-0.5 capitalize">{confidence}</p>
    </div>
  );
}

export default function PlanPage() {
  const [student, setStudent] = useState<Student | null>(null);
  const [plan, setPlan] = useState<LearningPlan | null>(null);
  const [days, setDays] = useState<LearningPlanDay[]>([]);
  const [skills, setSkills] = useState<SkillAssessment[]>([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const s = await getMyStudentProfile();
        setStudent(s);
        const [planResult, skillResult] = await Promise.allSettled([
          getLearningPlan(s.id),
          getStudentSkills(s.id),
        ]);
        if (planResult.status === "fulfilled") {
          setPlan(planResult.value.plan);
          setDays(planResult.value.days);
        }
        if (skillResult.status === "fulfilled") setSkills(skillResult.value.assessments);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const handleGenerate = async () => {
    if (!student) return;
    setGenerating(true);
    try {
      const p = await generateLearningPlan(student.id);
      setPlan(p.plan);
      setDays(p.days);
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

  const completed = days.filter((d) => d.status === "completed").length;
  const avgScore = days
    .filter((d) => d.score !== null)
    .reduce((acc, d, _, arr) => acc + (d.score ?? 0) / arr.length, 0);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">14-Day Learning Plan</h1>
          {plan && (
            <p className="mt-1 text-sm text-slate-500">
              {new Date(plan.start_date).toLocaleDateString()} – {new Date(plan.end_date).toLocaleDateString()}
            </p>
          )}
        </div>
        {!plan && (
          <button
            onClick={handleGenerate}
            disabled={generating}
            className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-50"
          >
            {generating ? "Generating…" : "Generate Plan"}
          </button>
        )}
      </div>

      {error && (
        <div className="rounded-xl bg-red-50 border border-red-200 p-4">
          <p className="text-sm text-red-700">{error}</p>
        </div>
      )}

      {plan && (
        <>
          {/* Stats */}
          <div className="grid grid-cols-3 gap-4">
            {[
              { label: "Days Completed", value: completed, color: "text-green-600" },
              { label: "Days Remaining", value: 14 - completed, color: "text-amber-600" },
              { label: "Avg Score", value: avgScore > 0 ? `${Math.round(avgScore)}/100` : "–", color: "text-indigo-600" },
            ].map((s) => (
              <div key={s.label} className="bg-white rounded-xl border border-slate-200 p-4">
                <p className="text-xs text-slate-500">{s.label}</p>
                <p className={`text-2xl font-bold mt-1 ${s.color}`}>{s.value}</p>
              </div>
            ))}
          </div>

          {/* Day grid */}
          <div>
            <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wide mb-3">Daily Schedule</h2>
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-7 gap-3">
              {days.map((d) => <DayCard key={d.id} day={d} />)}
            </div>
          </div>
        </>
      )}

      {/* Skill baseline */}
      {skills.length > 0 && (
        <div className="bg-white rounded-xl border border-slate-200 p-5">
          <h2 className="font-semibold text-slate-900 mb-4">Skill Baseline</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {skills
              .sort((a, b) => b.score - a.score)
              .map((s) => (
                <SkillBar key={s.dimension} dimension={s.dimension} score={s.score} confidence={s.confidence} />
              ))}
          </div>
        </div>
      )}

      {!plan && !generating && (
        <div className="bg-slate-50 rounded-xl border border-slate-200 p-12 text-center">
          <p className="text-slate-600 mb-3">No 14-day learning plan yet.</p>
          <p className="text-sm text-slate-500">Ask your mentor to generate one, or click Generate Plan above.</p>
        </div>
      )}
    </div>
  );
}
