import type { Dashboard, RunResult } from "../types";

const API_ROOT = import.meta.env.VITE_API_ROOT ?? "/api";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_ROOT}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail ?? `请求失败 (${response.status})`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  dashboard: () => request<Dashboard>("/dashboard"),
  run: (payload: { segment_id: string; objective: string; market_signal: string }) =>
    request<RunResult>("/runs", { method: "POST", body: JSON.stringify(payload) }),
  feedback: (payload: { run_id: string; converted: boolean; rating: number; note: string }) =>
    request<{ saved: boolean }>("/feedback", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
};
