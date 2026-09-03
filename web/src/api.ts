const BASE = "/v1";

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {}),
    },
  });
  const text = await resp.text();
  const data = text ? JSON.parse(text) : null;
  if (!resp.ok) {
    const detail = data?.detail ?? text ?? resp.statusText;
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return data as T;
}

export const api = {
  listProjects: () => req<Project[]>("/projects"),
  createProject: (body: unknown) =>
    req<Project>("/projects", { method: "POST", body: JSON.stringify(body) }),
  getProject: (id: string) => req<Project>(`/projects/${id}`),
  patchProject: (id: string, body: unknown) =>
    req<Project>(`/projects/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  ping: (id: string) =>
    req<Record<string, unknown>>(`/projects/${id}/adapter/ping`, { method: "POST" }),
  listDatasets: (pid: string) => req<Dataset[]>(`/projects/${pid}/datasets`),
  createDataset: (pid: string, body: unknown) =>
    req<Dataset>(`/projects/${pid}/datasets`, { method: "POST", body: JSON.stringify(body) }),
  listVersions: (ds: string) => req<Version[]>(`/datasets/${ds}/versions`),
  listCases: (vid: string) => req<EvalCase[]>(`/dataset-versions/${vid}/cases`),
  upsertCases: (vid: string, body: unknown) =>
    req<EvalCase[]>(`/dataset-versions/${vid}/cases`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  generate: (vid: string, hints: string[]) =>
    req<EvalCase[]>(`/dataset-versions/${vid}/generate`, {
      method: "POST",
      body: JSON.stringify({ hints }),
    }),
  confirm: (vid: string) =>
    req<Version>(`/dataset-versions/${vid}/confirm`, { method: "POST" }),
  sampleCalibration: (vid: string) =>
    req<Version>(`/dataset-versions/${vid}/sample-calibration`, {
      method: "POST",
      body: JSON.stringify({ per_type: 2, name: "calibration" }),
    }),
  listRuns: (pid: string) => req<Run[]>(`/projects/${pid}/runs`),
  createRun: (pid: string, body: unknown) =>
    req<Run>(`/projects/${pid}/runs`, { method: "POST", body: JSON.stringify(body) }),
  getRun: (id: string) => req<Run>(`/runs/${id}`),
  cancelRun: (id: string) => req<Run>(`/runs/${id}/cancel`, { method: "POST" }),
  runCases: (id: string) => req<CaseResult[]>(`/runs/${id}/cases`),
  patchHuman: (rid: string, caseId: string, body: unknown) =>
    req<CaseResult>(`/runs/${rid}/cases/${caseId}/human`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  report: (id: string) => req<Report>(`/runs/${id}/report`),
  diff: (a: string, b: string) => req<Diff>(`/runs/${a}/diff/${b}`),
  createExperiment: (pid: string, body: unknown) =>
    req<Experiment>(`/projects/${pid}/experiments`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  judgeStatus: (pid: string) => req<JudgeStatus>(`/projects/${pid}/judge-status`),
  listJudgeConfigs: (pid: string) => req<JudgeConfig[]>(`/projects/${pid}/judge-configs`),
  calibrate: (cfg: string, runId: string) =>
    req<Calibration>(`/judge-configs/${cfg}/calibrate`, {
      method: "POST",
      body: JSON.stringify({ run_id: runId }),
    }),
};

export type Project = {
  id: string;
  name: string;
  adapter_url: string;
  product_mode: string;
  spec: Record<string, unknown>;
  created_at: string;
};
export type Dataset = { id: string; project_id: string; kind: string; name: string };
export type Version = {
  id: string;
  dataset_id: string;
  version: number;
  confirmed_at: string | null;
  hash: string;
  case_count: number;
};
export type EvalCase = {
  id?: string;
  case_id: string;
  query: string;
  case_type: string;
  expected_behavior: string;
  expected_answer: string;
  expected_source: string[];
  supporting_passage: string[];
  tags: string[];
};
export type Run = {
  id: string;
  project_id: string;
  dataset_version_id: string;
  judge_config_id: string;
  fingerprint: string;
  status: string;
  total: number;
  done: number;
  pass_count: number;
  rag_version: Record<string, string>;
  error: string | null;
};
export type CaseResult = {
  id: string;
  case_id: string;
  actual_answer: string | null;
  judge_label: string | null;
  human_label: string | null;
  human_reason: string | null;
  primary_cause: string | null;
  evaluated_behavior: string | null;
  faithfulness: number | null;
  completeness: number | null;
  answer_relevancy: number | null;
  judge_reason: string | null;
  error: string | null;
};
export type Report = {
  fingerprint: string;
  pass_rate: number;
  n: number;
  means: Record<string, number | null>;
  retrieval_level: number;
  retrieval: Record<string, number>;
  slices: Record<string, { n: number; pass_rate: number; case_type: string; expected_behavior: string }>;
  primary_cause_dist: Record<string, number>;
  judge_status: string;
};
export type Diff = {
  metric_delta: Record<string, unknown>;
  fixed_fail_count: number;
  new_fail_count: number;
  still_fail_count: number;
  fingerprint_diff: { old: string; new: string; changed: boolean };
};
export type Experiment = {
  id: string;
  modified_variable: string;
  modified_from: string;
  modified_to: string;
};
export type JudgeStatus = { status: string; calibration: Calibration | null };
export type JudgeConfig = { id: string; provider: string; model: string; prompt_hash: string };
export type Calibration = {
  id: string;
  n: number;
  accuracy: number;
  false_pass_rate: number;
  false_fail_rate: number;
  status: string;
  confusion?: { tp: number; tn: number; fp: number; fn: number };
};
