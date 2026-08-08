export function ScoreBadge({ score, size = "lg" }: { score: number; size?: "sm" | "lg" }) {
  const color =
    score >= 8 ? "text-emerald-600 bg-emerald-50 border-emerald-200" :
    score >= 6 ? "text-amber-600 bg-amber-50 border-amber-200" :
                 "text-red-600 bg-red-50 border-red-200";

  return size === "lg" ? (
    <div className={`inline-flex flex-col items-center justify-center rounded-2xl border-2 px-6 py-4 ${color}`}>
      <span className="text-4xl font-bold tabular-nums">{score.toFixed(1)}</span>
      <span className="text-xs font-medium opacity-70 mt-0.5">/ 10</span>
    </div>
  ) : (
    <span className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-sm font-semibold ${color}`}>
      {score.toFixed(1)}
    </span>
  );
}
