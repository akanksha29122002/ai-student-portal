"use client";
import { useState, FormEvent } from "react";
import { useRouter } from "next/navigation";
import { login, getMe } from "@/lib/api";
import { saveTokens, saveUser } from "@/lib/auth";

const DEMO_ACCOUNTS = [
  { label: "Student Demo", sublabel: "Aarav Sharma", email: "student1@demo.projectdefense.ai", role: "student" },
  { label: "Mentor Demo",  sublabel: "Demo Mentor",  email: "mentor@demo.projectdefense.ai",  role: "mentor"  },
];
const DEMO_PASSWORD = "demo1234";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const tokens = await login(email, password);
      saveTokens(tokens);
      const user = await getMe();
      saveUser(user);
      router.push(user.role === "student" ? "/student" : "/mentor");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setLoading(false);
    }
  }

  async function demoLogin(demoEmail: string) {
    setEmail(demoEmail);
    setPassword(DEMO_PASSWORD);
    setError(null);
    setLoading(true);
    try {
      const tokens = await login(demoEmail, DEMO_PASSWORD);
      saveTokens(tokens);
      const user = await getMe();
      saveUser(user);
      router.push(user.role === "student" ? "/student" : "/mentor");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Demo login failed. Is the backend running?");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        {/* Logo / header */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-xl bg-indigo-600 mb-4">
            <svg className="w-7 h-7 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <h1 className="text-2xl font-bold text-slate-900">Project Defense AI</h1>
          <p className="text-sm text-slate-500 mt-1">AI-powered engineering evaluation</p>
        </div>

        {/* Demo quick-login */}
        {process.env.NEXT_PUBLIC_DEMO_MODE === "true" && (
          <div className="mb-6 p-4 rounded-xl border border-indigo-100 bg-indigo-50">
            <p className="text-xs font-semibold text-indigo-700 mb-3 uppercase tracking-wide">
              Demo Mode — Quick Login
            </p>
            <div className="grid grid-cols-2 gap-2">
              {DEMO_ACCOUNTS.map((acc) => (
                <button
                  key={acc.email}
                  onClick={() => demoLogin(acc.email)}
                  disabled={loading}
                  className="flex flex-col items-start p-3 rounded-lg bg-white border border-indigo-200 hover:border-indigo-400 hover:shadow-sm transition-all text-left disabled:opacity-50"
                >
                  <span className="text-sm font-semibold text-slate-800">{acc.label}</span>
                  <span className="text-xs text-slate-500 mt-0.5">{acc.sublabel}</span>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Form */}
        <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm">
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1.5">Email</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                placeholder="you@example.com"
                className="w-full rounded-lg border border-slate-200 px-3 py-2.5 text-sm text-slate-900 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1.5">Password</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                placeholder="••••••••"
                className="w-full rounded-lg border border-slate-200 px-3 py-2.5 text-sm text-slate-900 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
              />
            </div>

            {error && (
              <div className="rounded-lg bg-red-50 border border-red-200 px-3 py-2.5">
                <p className="text-sm text-red-700">{error}</p>
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 disabled:opacity-60 disabled:cursor-not-allowed transition-colors"
            >
              {loading ? "Signing in…" : "Sign In"}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
