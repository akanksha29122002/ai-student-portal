"use client";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import {
  getStudent, getStudentTasks, getStudentSubmissions,
  getStudentProfile, getStudentSkills, getStudentProgress,
  getReadinessReport, analyzeStudentProfile,
} from "@/lib/api";
import {
  Student, Task, Submission, StudentProfileAnalysis,
  SkillAssessment, ReadinessReport,
} from "@/lib/types";

function SkillBar({ dimension, score, confidence }: { dimension: string; score: number; confidence: string }) {
  const color = score >= 70 ? "bg-green-500" : score >= 40 ? "bg-amber-400" : "bg-red-400";
  const badge = confidence === "observed" ? "bg-green-100 text-green-700" : confidence === "inferred" ? "bg-amber-100 text-amber-700" : "bg-slate-100 text-slate-500";
  return (
    <div className="flex items-center gap-3">
      <div className="w-28 shrink-0">
        <p className="text-xs font-medium text-slate-700 truncate capitalize">{dimension.replace(/_/g, " ")}</p>
      </div>
      <div className="flex-1 h-2 bg-slate-100 rounded-full overflow-hidden">
        <div className={`h-full ${color} rounded-full`} style={{ width: `${score}%` }} />
      </div>
      <span className="text-xs font-semibold text-slate-700 w-8 text-right">{score}</span>
      <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium capitalize ${badge}`}>{confidence}</span>
    </div>
  );
}

function ReadinessCard({ report }: { report: ReadinessReport }) {
  const pct = Math.round(report.completion_rate * 100);
  return (
    <div className={`rounded-xl border p-5 ${report.ready_for_defense ? "bg-green-50 border-green-200" : "bg-amber-50 border-amber-200"}`}>
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-semibold text-slate-900">Readiness Report</h3>
        <span className={`rounded-full px-3 py-0.5 text-xs font-semibold ${report.ready_for_defense ? "bg-green-600 text-white" : "bg-amber-500 text-white"}`}>
          {report.ready_for_defense ? "Ready for Defense" : "Not Ready Yet"}
        </span>
      </div>
      <div className="grid grid-cols-3 gap-3 text-center">
        <div>
          <p className="text-2xl font-bold text-slate-900">{pct}%</p>
          <p className="text-xs text-slate-500">Complete</p>
        </div>
        <div>
          <p className="text-2xl font-bold text-slate-900">{report.completed_days}/{report.total_days}</p>
          <p className="text-xs text-slate-500">Days Done</p>
        </div>
        <div>
          <p className="text-2xl font-bold text-slate-900">{report.average_score !== null ? `${report.average_score}` : "–"}</p>
          <p className="text-xs text-slate-500">Avg Score</p>
        </div>
      </div>
    </div>
  );
}

type Tab = "overview" | "skills" | "tasks" | "submissions";

export default function StudentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [student, setStudent] = useState<Student | null>(null);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [submissions, setSubmissions] = useState<Submission[]>([]);
  const [profile, setProfile] = useState<StudentProfileAnalysis | null>(null);
  const [skills, setSkills] = useState<SkillAssessment[]>([]);
  const [report, setReport] = useState<ReadinessReport | null>(null);
  const [tab, setTab] = useState<Tab>("overview");
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    (async () => {
      try {
        const [s, t, sub] = await Promise.all([getStudent(id), getStudentTasks(id), getStudentSubmissions(id)]);
        setStudent(s);
        setTasks(t);
        setSubmissions(sub);
        const [profileResult, skillResult, reportResult] = await Promise.allSettled([
          getStudentProfile(id),
          getStudentSkills(id),
          getReadinessReport(id),
        ]);
        if (profileResult.status === "fulfilled") setProfile(profileResult.value);
        if (skillResult.status === "fulfilled") setSkills(skillResult.value.assessments);
        if (reportResult.status === "fulfilled") setReport(reportResult.value);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load");
      } finally {
        setLoading(false);
      }
    })();
  }, [id]);

  const handleAnalyze = async () => {
    if (!id) return;
    setAnalyzing(true);
    try {
      const p = await analyzeStudentProfile(id, {});
      setProfile(p);
      const [sk, rp] = await Promise.allSettled([getStudentSkills(id), getReadinessReport(id)]);
      if (sk.status === "fulfilled") setSkills(sk.value.assessments);
      if (rp.status === "fulfilled") setReport(rp.value);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Analysis failed");
    } finally {
      setAnalyzing(false);
    }
  };

  if (loading) return (
    <div className="flex items-center justify-center h-64">
      <div className="inline-block w-8 h-8 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin" />
    </div>
  );

  if (error || !student) return (
    <div className="rounded-xl bg-red-50 border border-red-200 p-4">
      <p className="text-sm text-red-700">{error ?? "Student not found"}</p>
    </div>
  );

  const TABS: { id: Tab; label: string }[] = [
    { id: "overview", label: "Overview" },
    { id: "skills", label: `Skills${skills.length ? ` (${skills.length})` : ""}` },
    { id: "tasks", label: `Tasks (${tasks.length})` },
    { id: "submissions", label: `Submissions (${submissions.length})` },
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">{student.full_name}</h1>
          <p className="mt-1 text-sm text-slate-500">{student.email} · Track {student.track.replace("track_", "").toUpperCase()}</p>
        </div>
        <button
          onClick={handleAnalyze}
          disabled={analyzing}
          className="rounded-lg bg-indigo-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-indigo-700 disabled:opacity-50"
        >
          {analyzing ? "Analyzing…" : profile ? "Re-analyze Profile" : "Analyze Profile"}
        </button>
      </div>

      {report && <ReadinessCard report={report} />}

      {/* Tabs */}
      <div className="border-b border-slate-200">
        <div className="flex gap-1">
          {TABS.map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
                tab === t.id
                  ? "border-indigo-600 text-indigo-600"
                  : "border-transparent text-slate-500 hover:text-slate-700"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>
      </div>

      {/* Tab content */}
      {tab === "overview" && (
        <div className="space-y-4">
          {profile ? (
            <>
              {profile.strengths.length > 0 && (
                <div className="bg-green-50 border border-green-100 rounded-xl p-4">
                  <h3 className="text-sm font-semibold text-green-800 mb-2">Strengths</h3>
                  <ul className="space-y-1">
                    {profile.strengths.map((s, i) => (
                      <li key={i} className="text-sm text-green-700 flex gap-2"><span>·</span>{s}</li>
                    ))}
                  </ul>
                </div>
              )}
              {profile.risk_factors.length > 0 && (
                <div className="bg-amber-50 border border-amber-100 rounded-xl p-4">
                  <h3 className="text-sm font-semibold text-amber-800 mb-2">Risk Factors</h3>
                  <ul className="space-y-1">
                    {profile.risk_factors.map((r, i) => (
                      <li key={i} className="text-sm text-amber-700">
                        <span className="font-medium">{r.factor}:</span> {r.description}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {profile.unknown_areas.length > 0 && (
                <div className="bg-slate-50 border border-slate-200 rounded-xl p-4">
                  <h3 className="text-sm font-semibold text-slate-700 mb-2">Insufficient Evidence</h3>
                  <div className="flex flex-wrap gap-1.5">
                    {profile.unknown_areas.map((a, i) => (
                      <span key={i} className="rounded-full bg-white border border-slate-200 text-xs px-2 py-0.5 text-slate-600">
                        {a.replace(/_/g, " ")}
                      </span>
                    ))}
                  </div>
                </div>
              )}
              {profile.learning_style && (
                <p className="text-sm text-slate-600">
                  <span className="font-medium">Learning style:</span>{" "}
                  <span className="capitalize">{profile.learning_style}</span>
                </p>
              )}
            </>
          ) : (
            <div className="bg-slate-50 rounded-xl border border-slate-200 p-6 text-center">
              <p className="text-slate-500 text-sm">No AI profile analysis yet.</p>
              <button onClick={handleAnalyze} disabled={analyzing} className="mt-2 text-sm text-indigo-600 hover:underline">
                {analyzing ? "Analyzing…" : "Analyze now →"}
              </button>
            </div>
          )}
        </div>
      )}

      {tab === "skills" && (
        <div className="bg-white rounded-xl border border-slate-200 p-5">
          {skills.length > 0 ? (
            <div className="space-y-3">
              {skills.sort((a, b) => b.score - a.score).map((s) => (
                <SkillBar key={s.dimension} dimension={s.dimension} score={s.score} confidence={s.confidence} />
              ))}
            </div>
          ) : (
            <p className="text-sm text-slate-500 text-center py-6">
              No skill assessments yet. Run profile analysis to generate baselines.
            </p>
          )}
        </div>
      )}

      {tab === "tasks" && (
        <div className="space-y-3">
          {tasks.length === 0 ? (
            <p className="text-sm text-slate-500">No tasks assigned.</p>
          ) : tasks.map((t) => (
            <div key={t.id} className="bg-white rounded-xl border border-slate-200 p-4">
              <p className="font-medium text-slate-900 text-sm">{t.title}</p>
              <p className="text-xs text-slate-500 mt-0.5">Due {new Date(t.due_on).toLocaleDateString()}</p>
            </div>
          ))}
        </div>
      )}

      {tab === "submissions" && (
        <div className="space-y-3">
          {submissions.length === 0 ? (
            <p className="text-sm text-slate-500">No submissions yet.</p>
          ) : submissions.map((s) => (
            <div key={s.id} className="bg-white rounded-xl border border-slate-200 p-4 flex justify-between items-center">
              <div>
                <p className="text-sm font-medium text-slate-900 capitalize">{s.self_status.replace(/_/g, " ")}</p>
                <p className="text-xs text-slate-500 mt-0.5">{new Date(s.created_at).toLocaleDateString()}</p>
              </div>
              <span className="text-xs bg-slate-100 text-slate-600 rounded-full px-2 py-0.5">{s.status}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
