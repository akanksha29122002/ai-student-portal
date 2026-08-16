"use client";
import { useEffect, useState } from "react";
import { getAccessToken } from "@/lib/auth";
import { VerificationResult } from "@/lib/types";

async function getEscalations(): Promise<{ total: number; items: VerificationResult[] }> {
  const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
  const token = getAccessToken();
  const res = await fetch(`${BASE}/mentor/escalations`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export default function EscalationsPage() {
  const [data, setData] = useState<{ total: number; items: VerificationResult[] } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getEscalations().then(setData).catch((e) => setError(e.message)).finally(() => setLoading(false));
  }, []);

  if (loading) return (
    <div className="flex items-center justify-center h-64">
      <div className="inline-block w-8 h-8 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin" />
    </div>
  );

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Escalation Queue</h1>
        <p className="mt-1 text-sm text-slate-500">Submissions flagged for mentor review by the automated verification engine.</p>
      </div>

      {error && (
        <div className="rounded-xl bg-red-50 border border-red-200 p-4">
          <p className="text-sm text-red-700">{error}</p>
        </div>
      )}

      {data && data.items.length === 0 && (
        <div className="bg-white rounded-xl border border-slate-200 p-12 text-center">
          <p className="text-slate-500">No escalations. All verifications passed or are pending.</p>
        </div>
      )}

      {data && data.items.length > 0 && (
        <div className="space-y-3">
          <p className="text-sm text-slate-500">{data.total} item{data.total !== 1 ? "s" : ""} in queue</p>
          {data.items.map((item) => (
            <div key={item.id} className="bg-white rounded-xl border border-amber-200 p-5">
              <div className="flex items-start justify-between">
                <div>
                  <p className="text-sm font-semibold text-slate-900">Submission {item.submission_id.slice(0, 8)}…</p>
                  {item.escalation_reason && (
                    <p className="text-xs text-amber-700 mt-1">{item.escalation_reason}</p>
                  )}
                  <div className="mt-2 flex items-center gap-3 text-xs text-slate-500">
                    {item.overall_score !== null && <span>Score: {item.overall_score}/100</span>}
                    {item.verdict && <span>Verdict: {item.verdict}</span>}
                    {item.completed_at && <span>{new Date(item.completed_at).toLocaleDateString()}</span>}
                  </div>
                </div>
                <span className="rounded-full bg-amber-100 text-amber-700 text-xs font-semibold px-2.5 py-0.5">
                  Needs Review
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
