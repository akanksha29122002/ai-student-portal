import { getAccessToken, clearAuth } from "./auth";
import {
  TokenResponse, UserResponse, Task, Submission, EvaluationResponse,
  Student, Batch, MentorDecision,
} from "./types";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function request<T>(
  path: string,
  opts: RequestInit = {},
  redirectOnUnauth = true,
): Promise<T> {
  const token = getAccessToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(opts.headers as Record<string, string> ?? {}),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${BASE}${path}`, { ...opts, headers });

  if (res.status === 401 && redirectOnUnauth) {
    clearAuth();
    if (typeof window !== "undefined") window.location.href = "/login";
    throw new Error("Unauthenticated");
  }

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail ?? `HTTP ${res.status}`);
  }

  if (res.status === 204) return undefined as T;
  return res.json();
}

// Auth
export const login = (email: string, password: string) =>
  request<TokenResponse>("/auth/token", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });

export const getMe = () => request<UserResponse>("/auth/me");

// Student self
export const getMyStudentProfile = () => request<Student>("/me/student");
export const getMyTasks = () => request<Task[]>("/me/tasks");
export const getMySubmissions = (taskId?: string) =>
  request<Submission[]>(`/me/submissions${taskId ? `?task_id=${taskId}` : ""}`);

// Tasks
export const getTask = (id: string) => request<Task>(`/tasks/${id}`);

// Submissions
export const createSubmission = (payload: {
  organization_id: string;
  task_id: string;
  student_id: string;
  self_status: string;
  commit_url?: string;
  approach_note?: string;
}) => request<Submission>("/submissions", { method: "POST", body: JSON.stringify(payload) });

// Evaluations
export const triggerEvaluation = (submissionId: string, force = false) =>
  request<EvaluationResponse>(`/submissions/${submissionId}/evaluate`, {
    method: "POST",
    body: JSON.stringify({ force_reevaluate: force }),
  });

export const getSubmissionEvaluation = (submissionId: string) =>
  request<EvaluationResponse>(`/submissions/${submissionId}/evaluation`);

export const getEvaluation = (evalId: string) =>
  request<EvaluationResponse>(`/evaluations/${evalId}`);

export const listEvaluations = (needsReviewOnly = false, limit = 50) =>
  request<EvaluationResponse[]>(
    `/evaluations/?needs_review_only=${needsReviewOnly}&limit=${limit}`,
  );

export const submitMentorReview = (
  evalId: string,
  decision: MentorDecision,
  feedback: string,
  overrideScore?: number,
) =>
  request<EvaluationResponse>(`/evaluations/${evalId}/mentor-review`, {
    method: "POST",
    body: JSON.stringify({
      decision,
      feedback,
      override_score: overrideScore ?? null,
    }),
  });

// Students / Batches (mentor)
export const listStudents = (orgId?: string) =>
  request<Student[]>(`/students${orgId ? `?org_id=${orgId}` : ""}`);

export const getStudent = (id: string) => request<Student>(`/students/${id}`);

export const getStudentTasks = (studentId: string) =>
  request<Task[]>(`/students/${studentId}/tasks`);

export const getStudentSubmissions = (studentId: string) =>
  request<Submission[]>(`/students/${studentId}/submissions`);

export const listBatches = () => request<Batch[]>("/batches");

// ---------------------------------------------------------------------------
// Milestone 7 — Learning Plans, Profile Analysis, Verification
// ---------------------------------------------------------------------------
import {
  LearningPlan, LearningPlanDay, SkillAssessment, StudentProfileAnalysis,
  StudentProgress, ReadinessReport, ImportResult,
} from "./types";

// Student — today's plan day
export const getTodayTask = (studentId: string) =>
  request<{ day: LearningPlanDay | null; task: Task | null }>(`/students/${studentId}/today`);

// Learning plan
export const generateLearningPlan = (studentId: string) =>
  request<{ plan: LearningPlan; days: LearningPlanDay[] }>(
    `/students/${studentId}/learning-plan`,
    { method: "POST" },
  );

export const getLearningPlan = (studentId: string) =>
  request<{ plan: LearningPlan; days: LearningPlanDay[] }>(
    `/students/${studentId}/learning-plan`,
  );

// Skill profile
export const analyzeStudentProfile = (studentId: string, rawProfile: Record<string, unknown> = {}) =>
  request<StudentProfileAnalysis>(`/students/${studentId}/analyze`, {
    method: "POST",
    body: JSON.stringify(rawProfile),
  });

export const getStudentProfile = (studentId: string) =>
  request<StudentProfileAnalysis>(`/students/${studentId}/profile`);

export const getStudentSkills = (studentId: string) =>
  request<{ student_id: string; assessments: SkillAssessment[] }>(
    `/students/${studentId}/skills`,
  );

// Progress
export const getStudentProgress = (studentId: string) =>
  request<{ student_id: string; progress_history: StudentProgress[]; current_skills: SkillAssessment[] }>(
    `/students/${studentId}/progress`,
  );

export const getReadinessReport = (studentId: string) =>
  request<ReadinessReport>(`/students/${studentId}/readiness-report`);

// Verification
export const verifySubmission = (submissionId: string) =>
  request<unknown>(`/submissions/${submissionId}/verify`, { method: "POST" });

// Import
export const importStudents = async (
  batchId: string,
  organizationId: string,
  file: File,
): Promise<ImportResult> => {
  const token = (await import("./auth")).getAccessToken();
  const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
  const form = new FormData();
  form.append("file", file);
  form.append("organization_id", organizationId);
  const res = await fetch(`${BASE}/import/batches/${batchId}/students`, {
    method: "POST",
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: form,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail ?? `HTTP ${res.status}`);
  }
  return res.json();
};
