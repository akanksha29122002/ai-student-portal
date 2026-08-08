const DIMENSION_LABELS: Record<string, string> = {
  correctness:       "Correctness",
  task_completeness: "Task Completeness",
  code_quality:      "Code Quality",
  architecture:      "Architecture",
  security:          "Security",
  performance:       "Performance",
  maintainability:   "Maintainability",
  edge_cases:        "Edge Cases",
  testing:           "Testing",
};

const DIMENSION_WEIGHTS: Record<string, number> = {
  correctness: 25, task_completeness: 20, code_quality: 15,
  architecture: 10, security: 10, performance: 5,
  maintainability: 5, edge_cases: 5, testing: 5,
};

function barColor(score: number) {
  if (score >= 8) return "bg-emerald-500";
  if (score >= 6) return "bg-amber-500";
  return "bg-red-500";
}

export function DimensionBar({
  name, score, reason,
}: { name: string; score: number; reason?: string }) {
  const label = DIMENSION_LABELS[name] ?? name;
  const weight = DIMENSION_WEIGHTS[name];
  const pct = (score / 10) * 100;

  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-slate-700">{label}</span>
          {weight && (
            <span className="text-xs text-slate-400">{weight}%</span>
          )}
        </div>
        <span className="text-sm font-semibold tabular-nums text-slate-800">
          {score.toFixed(1)}
        </span>
      </div>
      <div className="h-2 w-full rounded-full bg-slate-100">
        <div
          className={`h-2 rounded-full transition-all ${barColor(score)}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      {reason && (
        <p className="text-xs text-slate-500 leading-snug">{reason}</p>
      )}
    </div>
  );
}
