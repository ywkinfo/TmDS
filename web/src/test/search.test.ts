import { describe, expect, it } from "vitest";

import type { ReaderChapter } from "../lib/generated-data";
import { buildWarmedSearchState, rankSearchResults, resolveSearchNavigation, warmSearchEntries } from "../lib/search";

describe("search helpers", () => {
  it("falls back to a chapter route when section results are empty", () => {
    const chapters = [
      {
        id: "chapter-1",
        slug: "chapter-1",
        title: "제1장 목적",
        displayTitle: "제1장 목적",
        partTitle: "제1부 총 칙",
        summary: "요약",
        html: "",
        pageLabel: "10101",
        pageStart: 1,
        pageEnd: 2,
        hasImage: false,
        imageCount: 0,
        headings: [],
        sectionCatalog: [
          {
            id: "chapter-1-overview",
            chapterSlug: "chapter-1",
            chapterTitle: "제1장 목적",
            partTitle: "제1부 총 칙",
            sectionId: "overview",
            sectionTitle: "개요",
            text: "요약",
            excerpt: "요약",
            entryType: "overview",
            pageLabel: "10101",
            pageStart: 1,
            pageEnd: 1,
            hasImage: false,
            imageCount: 0,
            categories: [],
            routePath: "/chapter/chapter-1",
            compositeKey: "chapter-1-overview",
          },
        ],
        tocItemCount: 1,
      } satisfies ReaderChapter,
    ];

    const routePath = resolveSearchNavigation({
      query: "목적",
      results: [],
      activeIndex: 0,
      chapters,
    });

    expect(routePath).toBe("/chapter/chapter-1");
  });

  it("warms search entries with normalized haystacks", () => {
    const warmedEntries = warmSearchEntries([
      {
        id: "entry-1",
        chapterSlug: "chapter-1",
        chapterTitle: "제1장 목적",
        partTitle: "제1부 총 칙",
        sectionId: "overview",
        sectionTitle: "개요",
        text: "검색용 본문",
        excerpt: "요약",
        entryType: "overview",
        pageLabel: "10101",
        pageStart: 1,
        pageEnd: 1,
        hasImage: false,
        imageCount: 0,
        categories: [],
        routePath: "/chapter/chapter-1",
        compositeKey: "entry-1",
      },
    ]);

    expect(warmedEntries[0]?.normalizedHaystack).toContain("검색용본문");
  });

  it("returns explicit ready and empty warm states", () => {
    expect(
      buildWarmedSearchState([
        {
          id: "entry-1",
          chapterSlug: "chapter-1",
          chapterTitle: "제1장 목적",
          partTitle: "제1부 총 칙",
          sectionId: "overview",
          sectionTitle: "개요",
          text: "검색용 본문",
          excerpt: "요약",
          entryType: "overview",
          pageLabel: "10101",
          pageStart: 1,
          pageEnd: 1,
          hasImage: false,
          imageCount: 0,
          categories: [],
          routePath: "/chapter/chapter-1",
          compositeKey: "entry-1",
        },
      ]).status
    ).toBe("ready");

    expect(buildWarmedSearchState([]).status).toBe("empty");
  });

  it("does not rank unrelated overview entries when only one title matches", () => {
    const warmedEntries = warmSearchEntries([
      {
        id: "history-overview",
        chapterSlug: "history",
        chapterTitle: "제·개정 연혁",
        partTitle: "전문",
        sectionId: "overview",
        sectionTitle: "개요",
        text: "연혁 본문",
        excerpt: "연혁 요약",
        entryType: "overview",
        pageLabel: null,
        pageStart: 3,
        pageEnd: 3,
        hasImage: false,
        imageCount: 0,
        categories: [],
        routePath: "/chapter/history",
        compositeKey: "history-overview",
      },
      {
        id: "cover-overview",
        chapterSlug: "cover",
        chapterTitle: "표지",
        partTitle: "전문",
        sectionId: "overview",
        sectionTitle: "개요",
        text: "상표심사기준",
        excerpt: "표지 요약",
        entryType: "overview",
        pageLabel: null,
        pageStart: 1,
        pageEnd: 1,
        hasImage: false,
        imageCount: 0,
        categories: [],
        routePath: "/chapter/cover",
        compositeKey: "cover-overview",
      },
    ]);

    const results = rankSearchResults(warmedEntries, "제개정 연혁");

    expect(results.map((entry) => entry.chapterSlug)).toEqual(["history"]);
  });

  it("prefers exact section matches over part-level matches", () => {
    const warmedEntries = warmSearchEntries([
      {
        id: "part-cover",
        chapterSlug: "chapter-1",
        chapterTitle: "제1장 목적",
        partTitle: "제1부 총 칙",
        sectionId: "part-cover",
        sectionTitle: "총칙",
        text: "제1부 총 칙",
        excerpt: "총칙",
        entryType: "part-cover",
        pageLabel: null,
        pageStart: 23,
        pageEnd: 23,
        hasImage: true,
        imageCount: 1,
        categories: [],
        routePath: "/chapter/chapter-1/part-cover",
        compositeKey: "chapter-1-part-cover",
      },
      {
        id: "chapter-1-overview",
        chapterSlug: "chapter-1",
        chapterTitle: "제1장 목적",
        partTitle: "제1부 총 칙",
        sectionId: "overview",
        sectionTitle: "개요",
        text: "이 법은 상표를 보호함으로써...",
        excerpt: "목적 요약",
        entryType: "overview",
        pageLabel: "10101",
        pageStart: 25,
        pageEnd: 25,
        hasImage: false,
        imageCount: 0,
        categories: [],
        routePath: "/chapter/chapter-1",
        compositeKey: "chapter-1-overview",
      },
    ]);

    const results = rankSearchResults(warmedEntries, "총칙");

    expect(results[0]?.sectionId).toBe("part-cover");
  });

  it("surfaces search aliases for generic appendix revision queries", () => {
    const warmedEntries = warmSearchEntries([
      {
        id: "appendix-revision-alias",
        chapterSlug: "appendix-1",
        chapterTitle: "1. 심판관계서식례 및 기재례",
        partTitle: "부 록",
        sectionId: "part-intro",
        sectionTitle: "개정 연혁",
        text: "부 록 개정 연혁 개정내용 2021∼2023년 시행 산업재산권법 개정내용",
        excerpt: "개정 연혁",
        entryType: "search-alias",
        pageLabel: "1057",
        pageStart: 1057,
        pageEnd: 1344,
        hasImage: false,
        imageCount: 0,
        categories: ["appendix"],
        routePath: "/chapter/appendix-1/part-intro",
        compositeKey: "appendix-revision-alias",
      },
    ]);

    const results = rankSearchResults(warmedEntries, "개정 연혁");

    expect(results[0]?.entryType).toBe("search-alias");
    expect(results[0]?.routePath).toBe("/chapter/appendix-1/part-intro");
  });
});
