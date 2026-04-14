import { describe, expect, it } from "vitest";

import { compactSummary } from "../lib/formatters";

describe("compactSummary", () => {
  it("returns short text unchanged", () => {
    expect(compactSummary("짧은 요약입니다.", 40)).toBe("짧은 요약입니다.");
  });

  it("clips long text at a word boundary", () => {
    expect(compactSummary("이 문장은 카드에서 너무 길게 보여서 적당한 위치에서 줄여야 합니다.", 20)).toBe(
      "이 문장은 카드에서 너무 길게…"
    );
  });
});
