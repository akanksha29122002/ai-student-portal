type Status =
  | "completed" | "needs_human_review" | "pending" | "evaluating" | "failed"
  | "SOLVED" | "PARTIALLY_SOLVED" | "NOT_SOLVED" | "NEEDS_HUMAN_REVIEW"
  | "APPROVED" | "REJECTED" | "REQUEST_CHANGES"
  | string;

const styles: Record<string, string> = {
  completed:         "bg-emerald-50 text-emerald-700 border-emerald-200",
  SOLVED:            "bg-emerald-50 text-emerald-700 border-emerald-200",
  APPROVED:          "bg-emerald-50 text-emerald-700 border-emerald-200",
  needs_human_review:"bg-amber-50 text-amber-700 border-amber-200",
  NEEDS_HUMAN_REVIEW:"bg-amber-50 text-amber-700 border-amber-200",
  PARTIALLY_SOLVED:  "bg-amber-50 text-amber-700 border-amber-200",
  REQUEST_CHANGES:   "bg-amber-50 text-amber-700 border-amber-200",
  pending:           "bg-slate-50 text-slate-600 border-slate-200",
  evaluating:        "bg-blue-50 text-blue-700 border-blue-200",
  context_building:  "bg-blue-50 text-blue-700 border-blue-200",
  validating:        "bg-blue-50 text-blue-700 border-blue-200",
  NOT_SOLVED:        "bg-red-50 text-red-700 border-red-200",
  REJECTED:          "bg-red-50 text-red-700 border-red-200",
  failed:            "bg-red-50 text-red-700 border-red-200",
};

const labels: Record<string, string> = {
  completed:          "Completed",
  needs_human_review: "Needs Review",
  NEEDS_HUMAN_REVIEW: "Needs Review",
  pending:            "Pending",
  evaluating:         "Evaluating",
  context_building:   "Building Context",
  validating:         "Validating",
  SOLVED:             "Solved",
  PARTIALLY_SOLVED:   "Partially Solved",
  NOT_SOLVED:         "Not Solved",
  APPROVED:           "Approved",
  REJECTED:           "Rejected",
  REQUEST_CHANGES:    "Changes Requested",
  failed:             "Failed",
};

export function StatusChip({ status }: { status: Status }) {
  const cls = styles[status] ?? "bg-slate-50 text-slate-600 border-slate-200";
  const label = labels[status] ?? status;
  return (
    <span className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium ${cls}`}>
      {label}
    </span>
  );
}
