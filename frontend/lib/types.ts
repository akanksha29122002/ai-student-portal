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
