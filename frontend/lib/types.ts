// API response types matching the FastAPI backend schemas

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface UserResponse {
  id: string;
  email: string;
  full_name: string;
  role: "super_admin" | "organization_admin" | "program_manager" | "mentor" | "student" | "ai_agent" | "system";
  organization_id: string | null;
  is_active: boolean;
}

export interface Organization {
  id: string;
  name: string;
  slug: string;
}

export interface Batch {
  id: string;
  organization_id: string;
  name: string;
  starts_on: string;
  ends_on: string;
}

export interface Student {
  id: string;
  organization_id: string;
  batch_id: string;
  full_name: string;
  email: string;
  track: string;
  mentor_id: string | null;
}

export interface Task {
  id: string;
  organization_id: string;
  batch_id: string;
  student_id: string;
  project_id: string;
  task_type: "coding" | "spoken_question";
  title: string;
  problem_statement: string;
  acceptance_criteria: string[];
  expected_concepts: string[];
  due_on: string;
  created_at: string;
}

export interface Submission {
  id: string;
  organization_id: string;
  task_id: string;
  student_id: string;
  self_status: "solved" | "partially_solved" | "not_solved" | "attempted" | "skipped";
  commit_url: string | null;
  repository_url: string | null;
  approach_note: string | null;
  status: string;
  created_at: string;
}

export interface DimensionScore {
  score: number;
  reason: string;
  evidence: EvidenceItem[];
}

export interface EvaluationDimensions {
  correctness: DimensionScore;
  task_completeness: DimensionScore;
  code_quality: DimensionScore;
  architecture: DimensionScore;
  security: DimensionScore;
  performance: DimensionScore;
  maintainability: DimensionScore;
  edge_cases: DimensionScore;
  testing: DimensionScore;
}

export interface EvidenceItem {
  file: string;
  line: number | null;
  type: string;
  severity: "critical" | "high" | "medium" | "low" | "info";
  description: string;
}

export interface CriterionResult {
  criterion: string;
  status: "PASS" | "PARTIAL" | "FAIL" | "CANNOT_VERIFY";
  evidence: string[];
  notes: string;
}

export interface EvaluationResult {
  status: "SOLVED" | "PARTIALLY_SOLVED" | "NOT_SOLVED" | "NEEDS_HUMAN_REVIEW";
  overall_score: number;
  confidence: number;
  dimensions: EvaluationDimensions;
  acceptance_criteria_results: CriterionResult[];
  strengths: string[];
  issues: EvidenceItem[];
  missing_requirements: string[];
  security_concerns: EvidenceItem[];
  performance_concerns: EvidenceItem[];
  suggested_improvements: string[];
  mentor_attention_required: boolean;
  mentor_attention_reasons: string[];
  summary: string;
}

export interface EvaluationResponse {
  evaluation_id: string;
  submission_id: string;
  state: "pending" | "context_building" | "evaluating" | "validating" | "completed" | "needs_human_review" | "failed";
  result: EvaluationResult | null;
  provider: string;
  model: string;
  mock_mode: boolean;
  context_hash: string;
  input_tokens: number;
  output_tokens: number;
  duration_ms: number;
  error: string | null;
  created_at: string;
  updated_at: string;
  mentor_decision: "APPROVED" | "REJECTED" | "REQUEST_CHANGES" | "OVERRIDE_SCORE" | null;
  mentor_feedback: string | null;
}

export type MentorDecision = "APPROVED" | "REJECTED" | "REQUEST_CHANGES" | "OVERRIDE_SCORE";

// ---------------------------------------------------------------------------
// Milestone 7 — Learning Plans
// ---------------------------------------------------------------------------

export type PlanDayStatus = "locked" | "available" | "in_progress" | "completed" | "skipped" | "blocked";
export type LearningPlanStatus = "draft" | "active" | "completed" | "abandoned";

export interface LearningPlan {
  id: string;
  student_id: string;
  organization_id: string;
  batch_id: string;
  status: LearningPlanStatus;
  start_date: string;
  end_date: string;
  total_days: number;
  created_at: string;
}

export interface LearningPlanDay {
  id: string;
  plan_id: string;
  student_id: string;
  day_number: number;
  scheduled_date: string;
  status: PlanDayStatus;
  task_id: string | null;
  target_skills: string[];
  unlock_condition: Record<string, unknown> | null;
  completed_at: string | null;
  score: number | null;
  notes: string | null;
}

export interface SkillAssessment {
  id: string;
  student_id: string;
  dimension: string;
  score: number;
  confidence: "observed" | "inferred" | "unknown";
  assessed_at: string;
}

export interface StudentProfileAnalysis {
  id: string;
  student_id: string;
  status: "pending" | "running" | "complete" | "failed";
  observed_skills: Array<{ name: string; level: string; evidence: string }>;
  inferred_skills: Array<{ name: string; level: string; reasoning: string }>;
  unknown_areas: string[];
  learning_style: string | null;
  risk_factors: Array<{ factor: string; description: string }>;
  strengths: string[];
  ai_model: string | null;
  confidence: number | null;
  generated_at: string | null;
}

export interface VerificationResult {
  id: string;
  submission_id: string;
  status: "pending" | "running" | "passed" | "failed" | "needs_human_review" | "error";
  overall_score: number | null;
  verdict: string | null;
  escalate_to_mentor: boolean;
  escalation_reason: string | null;
  completed_at: string | null;
}

export interface StudentProgress {
  id: string;
  student_id: string;
  snapshot_date: string;
  day_number: number | null;
  days_completed: number;
  days_remaining: number;
  current_streak: number;
  longest_streak: number;
  average_score: number | null;
}

export interface ReadinessReport {
  student_id: string;
  student_name: string;
  plan_id: string | null;
  total_days: number;
  completed_days: number;
  average_score: number | null;
  completion_rate: number;
  total_submissions: number;
  skill_summary: Array<{ dimension: string; score: number; confidence: string }>;
  strengths: string[];
  risk_factors: Array<{ factor: string; description: string }>;
  ready_for_defense: boolean;
}

export interface ImportResult {
  imported: number;
  skipped: number;
  errors: Array<{ row: number; email?: string; reason: string }>;
  student_ids: string[];
  generated_passwords: Array<{ email: string; password: string }>;
}
