import { describe, expect, it } from "vitest";
import { formatDuration, formatPercent, shortId } from "./format";

describe("format helpers", () => {
  it("formats rates as percentages", () => {
    expect(formatPercent(0.423)).toBe("42.3%");
  });

  it("formats short durations", () => {
    expect(formatDuration("2026-01-01T00:00:00.000Z", "2026-01-01T00:00:00.120Z")).toBe(
      "120 ms",
    );
  });

  it("shortens run ids", () => {
    expect(shortId("run_abcdef123456")).toBe("#ABCDEF12");
  });
});
