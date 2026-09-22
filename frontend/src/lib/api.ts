import type { Dashboard, RunResult, Job, Document, Memory, Evaluation, Experiment, Report, Citation, Passport } from "../types";

const API_ROOT = import.meta.env.VITE_API_ROOT ?? "/api";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_ROOT}${path}`, {
    signal: AbortSignal.timeout(15000),
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const detail = body?.detail;
    throw new Error(typeof detail === "string" ? detail : `输入不合法或服务异常 (${response.status})`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  jobs: () => request<Job[]>("/jobs"),
  job: (id: string) => request<Job>(`/jobs/${id}`),
  submit: (payload: RunResult["request"], key: string) => request<Job>("/jobs", {
    method: "POST", headers: {"Idempotency-Key": key}, body: JSON.stringify(payload),
  }),
  retry: (id: string) => request<Job>(`/jobs/${id}/retry`, {method: "POST"}),
  getRun: (id: string) => request<RunResult>(`/runs/${id}`),
  runs: () => request<RunResult[]>("/runs?limit=100"),
  knowledge: () => request<Document[]>("/knowledge"),
  search: (query: string) => request<{results: Citation[]}>(`/knowledge/search?q=${encodeURIComponent(query)}`),
  memories: () => request<Memory[]>("/memories"),
  memoryState: (id: string, active: boolean) => request(`/memories/${id}`, {
    method: "PATCH", body: JSON.stringify({active}),
  }),
  configuration: () => request<Record<string, string | number | boolean>>("/configuration"),
  evaluate: () => request<Evaluation>("/evals/run", {method: "POST"}),
  evaluations: () => request<Report<Evaluation>[]>("/evals/reports"),
  experiment: (payload: Experiment["request"]) => request<Experiment>("/experiments", {
    method: "POST", body: JSON.stringify(payload),
  }),
  experiments: () => request<Report<Experiment>[]>("/experiments"),
  evidence: (id: string) => request<Passport>(`/runs/${id}/evidence`),
  review: (id: string) => request<{rating: number; note: string; endorsed: number} | null>(`/runs/${id}/review`),
  dashboard: () => request<Dashboard>("/dashboard"),
  run: (payload: { segment_id: string; objective: string; market_signal: string }) =>
    request<RunResult>("/runs", { method: "POST", body: JSON.stringify(payload) }),
  feedback: (payload: { run_id: string; converted: boolean; rating: number; note: string }) =>
    request<{ saved: boolean }>("/feedback", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
};
