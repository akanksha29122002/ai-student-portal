"use client";
import { useEffect, useRef, useState } from "react";
import { importStudents, listBatches } from "@/lib/api";
import { Batch, ImportResult } from "@/lib/types";

export default function ImportStudentsPage() {
  const [batches, setBatches] = useState<Batch[]>([]);
  const [batchId, setBatchId] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ImportResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    listBatches().then(setBatches).catch(() => {});
  }, []);

  const orgId = batches.find((b) => b.id === batchId)?.organization_id ?? "";

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file || !batchId || !orgId) {
      setError("Select a batch and upload a file.");
      return;
    }
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const r = await importStudents(batchId, orgId, file);
      setResult(r);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Import failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Import Students</h1>
        <p className="mt-1 text-sm text-slate-500">
          Upload a CSV, XLSX, or JSON file to bulk-create student accounts.
          Required columns: <code className="bg-slate-100 px-1 rounded text-xs">email</code>,{" "}
          <code className="bg-slate-100 px-1 rounded text-xs">name</code> or{" "}
          <code className="bg-slate-100 px-1 rounded text-xs">full_name</code>.
          Optional: <code className="bg-slate-100 px-1 rounded text-xs">track</code>,{" "}
          <code className="bg-slate-100 px-1 rounded text-xs">password</code>.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="bg-white rounded-xl border border-slate-200 p-6 space-y-5">
        {/* Batch selector */}
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">Batch</label>
          <select
            value={batchId}
            onChange={(e) => setBatchId(e.target.value)}
            required
            className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
          >
            <option value="">Select a batch…</option>
            {batches.map((b) => (
              <option key={b.id} value={b.id}>{b.name}</option>
            ))}
          </select>
        </div>

        {/* File upload */}
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">Roster File</label>
          <div
            className="border-2 border-dashed border-slate-300 rounded-lg p-6 text-center cursor-pointer hover:border-indigo-400 transition-colors"
            onClick={() => fileRef.current?.click()}
          >
            {file ? (
              <p className="text-sm text-slate-700 font-medium">{file.name} ({(file.size / 1024).toFixed(1)} KB)</p>
            ) : (
              <>
                <p className="text-slate-500 text-sm">Click to select or drag & drop</p>
                <p className="text-xs text-slate-400 mt-1">CSV · XLSX · JSON</p>
              </>
            )}
          </div>
          <input
            ref={fileRef}
            type="file"
            accept=".csv,.xlsx,.xls,.json"
            className="hidden"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          />
        </div>

        {error && (
          <div className="rounded-lg bg-red-50 border border-red-200 p-3">
            <p className="text-sm text-red-700">{error}</p>
          </div>
        )}

        <button
          type="submit"
          disabled={loading || !file || !batchId}
          className="w-full rounded-lg bg-indigo-600 py-2.5 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-50 transition-colors"
        >
          {loading ? "Importing…" : "Import Students"}
        </button>
      </form>

      {result && (
        <div className="bg-white rounded-xl border border-slate-200 p-6 space-y-4">
          <h2 className="font-semibold text-slate-900">Import Result</h2>

          <div className="grid grid-cols-3 gap-4">
            <div className="bg-green-50 rounded-lg p-3 text-center">
              <p className="text-2xl font-bold text-green-600">{result.imported}</p>
              <p className="text-xs text-green-700 mt-0.5">Imported</p>
            </div>
            <div className="bg-amber-50 rounded-lg p-3 text-center">
              <p className="text-2xl font-bold text-amber-600">{result.skipped}</p>
              <p className="text-xs text-amber-700 mt-0.5">Skipped</p>
            </div>
            <div className="bg-slate-50 rounded-lg p-3 text-center">
              <p className="text-2xl font-bold text-slate-700">{result.errors.length}</p>
              <p className="text-xs text-slate-500 mt-0.5">Errors</p>
            </div>
          </div>

          {result.generated_passwords.length > 0 && (
            <div>
              <h3 className="text-sm font-semibold text-slate-700 mb-2">
                Generated Passwords <span className="text-red-600 font-normal">(save these now — shown only once)</span>
              </h3>
              <div className="rounded-lg bg-amber-50 border border-amber-200 p-3 space-y-1 max-h-48 overflow-y-auto">
                {result.generated_passwords.map((gp) => (
                  <div key={gp.email} className="flex justify-between text-xs">
                    <span className="text-slate-700 font-medium">{gp.email}</span>
                    <span className="font-mono text-amber-800">{gp.password}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {result.errors.length > 0 && (
            <div>
              <h3 className="text-sm font-semibold text-slate-700 mb-2">Errors</h3>
              <div className="space-y-1 max-h-40 overflow-y-auto">
                {result.errors.map((err, i) => (
                  <div key={i} className="rounded-lg bg-red-50 border border-red-100 px-3 py-2 text-xs text-red-700">
                    Row {err.row}{err.email ? ` (${err.email})` : ""}: {err.reason}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
