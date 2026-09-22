import { afterEach, describe, expect, it, vi } from "vitest";
import { api } from "./api";

afterEach(() => vi.unstubAllGlobals());

describe("API boundary", () => {
  it("preserves the request identity across network retries", async () => {
    const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({id: "job-one"})));
    vi.stubGlobal("fetch", fetch);
    const payload = {segment_id: "steady-planner", objective: "投资者教育", market_signal: "市场波动上升", dry_run: true, seed: 42, variant: "clarity"};
    const result = await api.submit(payload, "stable-request-key");
    expect(result.id).toBe("job-one");
    const [url, init] = fetch.mock.calls[0];
    expect(url).toBe("/api/jobs");
    expect(init.headers["Idempotency-Key"]).toBe("stable-request-key");
    expect(JSON.parse(init.body)).toEqual(payload);
    expect(init.signal).toBeInstanceOf(AbortSignal);
  });

  it("shows actionable duplicate/conflict messages", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({detail: "该运行已经复核"}), {status: 409})));
    await expect(api.retry("job-one")).rejects.toThrow("该运行已经复核");
  });

  it("does not render structured validation objects as text", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({detail: [{loc: ["seed"], msg: "invalid"}]}), {status: 422})));
    await expect(api.jobs()).rejects.toThrow("输入不合法或服务异常 (422)");
  });

  it("handles a non-JSON server failure", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("unavailable", {status: 503})));
    await expect(api.jobs()).rejects.toThrow("输入不合法或服务异常 (503)");
  });

  it("encodes knowledge queries without changing the request route", async () => {
    const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({results: []})));
    vi.stubGlobal("fetch", fetch);
    await api.search("风险 & 来源");
    expect(fetch.mock.calls[0][0]).toBe(`/api/knowledge/search?q=${encodeURIComponent("风险 & 来源")}`);
  });
});
