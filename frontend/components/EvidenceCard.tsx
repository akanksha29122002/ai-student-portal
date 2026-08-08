import { EvidenceItem } from "@/lib/types";

const severityStyle: Record<string, string> = {
  critical: "border-l-red-500 bg-red-50",
  high:     "border-l-orange-500 bg-orange-50",
  medium:   "border-l-amber-500 bg-amber-50",
  low:      "border-l-blue-500 bg-blue-50",
  info:     "border-l-slate-400 bg-slate-50",
};

const severityLabel: Record<string, string> = {
  critical: "Critical", high: "High", medium: "Medium", low: "Low", info: "Info",
};

export function EvidenceCard({ item }: { item: EvidenceItem }) {
  const cls = severityStyle[item.severity] ?? "border-l-slate-400 bg-slate-50";
  return (
    <div className={`border-l-4 rounded-r-lg p-3 ${cls}`}>
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1">
          <p className="text-sm font-medium text-slate-800">{item.description}</p>
          {item.file && (
            <p className="mt-1 font-mono text-xs text-slate-500">
              {item.file}{item.line ? `:${item.line}` : ""}
            </p>
          )}
        </div>
        <span className="shrink-0 rounded-full px-2 py-0.5 text-xs font-medium bg-white border border-current opacity-80">
          {severityLabel[item.severity] ?? item.severity}
        </span>
      </div>
    </div>
  );
}
