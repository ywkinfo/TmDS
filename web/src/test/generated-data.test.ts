import { describe, expect, it } from "vitest";

import { adaptGeneratedData, resolveCanonicalChapterRoute } from "../lib/generated-data";

describe("adaptGeneratedData", () => {
  it("synthesizes overview entries and resolves exploration links with chapter-aware composite keys", () => {
    const data = adaptGeneratedData({
      manifest: {
        title: "상표심사기준",
        syncedAt: "2026-04-11T00:00:00.000Z",
        fileCount: 5,
        imageFileCount: 0,
      },
      toc: {
        meta: {
          title: "상표심사기준",
          partCount: 1,
          chapterCount: 2,
          itemCount: 2,
          supplementCount: 0,
        },
        parts: [
          {
            id: "part-1",
            label: "제1부",
            title: "총 칙",
            fullTitle: "제1부 총 칙",
            chapters: [
              {
                id: "chapter-a",
                label: "제1장",
                title: "제1장 목적",
                fullTitle: "제1장 목적",
                pageLabel: "10101",
                items: [{ id: "shared-section" }],
                supplements: [],
              },
              {
                id: "chapter-b",
                label: "제2장",
                title: "제2장 심사",
                fullTitle: "제2장 심사",
                pageLabel: "10201",
                items: [{ id: "shared-section" }],
                supplements: [],
              },
            ],
          },
        ],
      },
      documentData: {
        meta: {
          title: "상표심사기준",
          builtAt: "2026-04-11T00:00:00.000Z",
          chapterCount: 2,
          pageCount: 4,
          partCount: 1,
        },
        chapters: [
          {
            id: "chapter-a",
            slug: "chapter-a",
            title: "제1장 목적",
            summary: "첫 번째 장 요약",
            html: '<section id="overview"><h2>제1장 목적</h2></section><section id="shared-section"><h3>공통 항목</h3></section>',
            hasImage: false,
            imageCount: 0,
            headings: [{ id: "shared-section", depth: 3, title: "공통 항목" }],
            partTitle: "제1부 총 칙",
            pageLabel: "10101",
            pageStart: 1,
            pageEnd: 2,
          },
          {
            id: "chapter-b",
            slug: "chapter-b",
            title: "제2장 심사",
            summary: "두 번째 장 요약",
            html: '<section id="overview"><h2>제2장 심사</h2></section><section id="shared-section"><h3>공통 항목</h3></section>',
            hasImage: false,
            imageCount: 0,
            headings: [{ id: "shared-section", depth: 3, title: "공통 항목" }],
            partTitle: "제1부 총 칙",
            pageLabel: "10201",
            pageStart: 3,
            pageEnd: 4,
          },
        ],
      },
      searchIndex: [
        {
          id: "shared-section",
          chapterSlug: "chapter-a",
          chapterTitle: "제1장 목적",
          sectionId: "shared-section",
          sectionTitle: "공통 항목",
          text: "alpha",
          excerpt: "alpha excerpt",
          entryType: "item",
          partTitle: "제1부 총 칙",
          pageLabel: "10101",
          pageStart: 2,
          pageEnd: 2,
          hasImage: false,
          imageCount: 0,
          categories: [],
        },
        {
          id: "shared-section",
          chapterSlug: "chapter-b",
          chapterTitle: "제2장 심사",
          sectionId: "shared-section",
          sectionTitle: "공통 항목",
          text: "beta",
          excerpt: "beta excerpt",
          entryType: "item",
          partTitle: "제1부 총 칙",
          pageLabel: "10201",
          pageStart: 4,
          pageEnd: 4,
          hasImage: false,
          imageCount: 0,
          categories: ["procedure"],
        },
      ],
      explorationIndex: [
        {
          id: "shared-section",
          title: "공통 항목",
          chapterTitle: "제2장 심사",
          partTitle: "제1부 총 칙",
          categories: ["procedure"],
          pageLabel: "10201",
          pageStart: 4,
          pageEnd: 4,
          hasImage: false,
          excerpt: "beta excerpt",
        },
      ],
    });

    expect(data.chapterMap.get("chapter-a")?.sectionCatalog[0]?.sectionId).toBe("overview");
    expect(data.chapterMap.get("chapter-b")?.sectionCatalog[0]?.sectionId).toBe("overview");
    expect(data.explorationEntries[0]?.routePath).toBe("/chapter/chapter-b/shared-section");
  });

  it("normalizes invalid section routes back to the canonical chapter route", () => {
    const data = adaptGeneratedData({
      manifest: {
        title: "상표심사기준",
        syncedAt: "2026-04-11T00:00:00.000Z",
        fileCount: 5,
        imageFileCount: 0,
      },
      toc: {
        meta: {
          title: "상표심사기준",
          partCount: 1,
          chapterCount: 1,
          itemCount: 1,
          supplementCount: 0,
        },
        parts: [
          {
            id: "part-1",
            label: "제1부",
            title: "총 칙",
            fullTitle: "제1부 총 칙",
            chapters: [
              {
                id: "chapter-a",
                label: "제1장",
                title: "제1장 목적",
                fullTitle: "제1장 목적",
                pageLabel: "10101",
                items: [{ id: "section-1" }],
                supplements: [],
              },
            ],
          },
        ],
      },
      documentData: {
        meta: {
          title: "상표심사기준",
          builtAt: "2026-04-11T00:00:00.000Z",
          chapterCount: 1,
          pageCount: 2,
          partCount: 1,
        },
        chapters: [
          {
            id: "chapter-a",
            slug: "chapter-a",
            title: "제1장 목적",
            summary: "첫 번째 장 요약",
            html: '<section id="overview"><h2>제1장 목적</h2></section><section id="section-1"><h3>첫 항목</h3></section>',
            hasImage: false,
            imageCount: 0,
            headings: [{ id: "section-1", depth: 3, title: "첫 항목" }],
            partTitle: "제1부 총 칙",
            pageLabel: "10101",
            pageStart: 1,
            pageEnd: 2,
          },
        ],
      },
      searchIndex: [
        {
          id: "section-1",
          chapterSlug: "chapter-a",
          chapterTitle: "제1장 목적",
          sectionId: "section-1",
          sectionTitle: "첫 항목",
          text: "alpha",
          excerpt: "alpha excerpt",
          entryType: "item",
          partTitle: "제1부 총 칙",
          pageLabel: "10101",
          pageStart: 2,
          pageEnd: 2,
          hasImage: false,
          imageCount: 0,
          categories: [],
        },
      ],
      explorationIndex: [],
    });

    const chapter = data.chapterMap.get("chapter-a");
    expect(chapter).toBeDefined();

    const invalidSection = resolveCanonicalChapterRoute(chapter!, "does-not-exist");
    expect(invalidSection.activeSectionId).toBe("overview");
    expect(invalidSection.canonicalPath).toBe("/chapter/chapter-a");

    const overviewSection = resolveCanonicalChapterRoute(chapter!, "overview");
    expect(overviewSection.canonicalPath).toBe("/chapter/chapter-a");
  });

  it("orders part-intro entries before overview and redirects bare chapter routes to them", () => {
    const data = adaptGeneratedData({
      manifest: {
        title: "상표심사기준",
        syncedAt: "2026-04-11T00:00:00.000Z",
        fileCount: 5,
        imageFileCount: 0,
      },
      toc: {
        meta: {
          title: "상표심사기준",
          partCount: 1,
          chapterCount: 1,
          itemCount: 1,
          supplementCount: 0,
        },
        parts: [
          {
            id: "part-4",
            label: "제4부",
            title: "상표등록의 요건",
            fullTitle: "제4부 상표등록의 요건",
            chapters: [
              {
                id: "chapter-4-1",
                label: "제1장",
                title: "제1장 상품의 보통명칭인 상표",
                fullTitle: "제1장 상품의 보통명칭인 상표",
                pageLabel: "40101",
                items: [{ id: "section-1" }],
                supplements: [],
              },
            ],
          },
        ],
      },
      documentData: {
        meta: {
          title: "상표심사기준",
          builtAt: "2026-04-11T00:00:00.000Z",
          chapterCount: 1,
          pageCount: 3,
          partCount: 1,
        },
        chapters: [
          {
            id: "chapter-4-1",
            slug: "chapter-4-1",
            title: "제1장 상품의 보통명칭인 상표",
            summary: "상표의 식별력 요약",
            html: '<section id="overview"><h2>제1장 상품의 보통명칭인 상표</h2></section><section id="part-intro"><h3>상표의 식별력</h3></section><section id="section-1"><h3>1. 적용요건</h3></section>',
            hasImage: false,
            imageCount: 0,
            headings: [{ id: "section-1", depth: 3, title: "1. 적용요건" }],
            partTitle: "제4부 상표등록의 요건",
            pageLabel: "40101",
            pageStart: 161,
            pageEnd: 162,
          },
        ],
      },
      searchIndex: [
        {
          id: "chapter-4-1-part-intro",
          chapterSlug: "chapter-4-1",
          chapterTitle: "제1장 상품의 보통명칭인 상표",
          sectionId: "part-intro",
          sectionTitle: "상표의 식별력",
          text: "식별력 도입 본문",
          excerpt: "식별력 도입 요약",
          entryType: "part-intro",
          partTitle: "제4부 상표등록의 요건",
          pageLabel: null,
          pageStart: 159,
          pageEnd: 160,
          hasImage: false,
          imageCount: 0,
          categories: [],
        },
        {
          id: "section-1",
          chapterSlug: "chapter-4-1",
          chapterTitle: "제1장 상품의 보통명칭인 상표",
          sectionId: "section-1",
          sectionTitle: "1. 적용요건",
          text: "적용요건 본문",
          excerpt: "적용요건 요약",
          entryType: "item",
          partTitle: "제4부 상표등록의 요건",
          pageLabel: "40101",
          pageStart: 161,
          pageEnd: 162,
          hasImage: false,
          imageCount: 0,
          categories: [],
        },
      ],
      explorationIndex: [
        {
          id: "chapter-4-1-part-intro",
          title: "상표의 식별력",
          chapterTitle: "제1장 상품의 보통명칭인 상표",
          partTitle: "제4부 상표등록의 요건",
          categories: [],
          pageLabel: null,
          pageStart: 159,
          pageEnd: 160,
          hasImage: false,
          excerpt: "식별력 도입 요약",
        },
      ],
    });

    const chapter = data.chapterMap.get("chapter-4-1");
    expect(chapter?.sectionCatalog.map((entry) => entry.sectionId)).toEqual(["part-intro", "overview", "section-1"]);
    expect(resolveCanonicalChapterRoute(chapter!, undefined).canonicalPath).toBe("/chapter/chapter-4-1/part-intro");
    expect(data.explorationEntries[0]?.routePath).toBe("/chapter/chapter-4-1/part-intro");
  });

  it("keeps chapter-level null pageLabel for synthetic chapters and resolves overview routes normally", () => {
    const data = adaptGeneratedData({
      manifest: {
        title: "상표심사기준",
        syncedAt: "2026-04-13T00:00:00.000Z",
        fileCount: 5,
        imageFileCount: 0,
      },
      toc: {
        meta: {
          title: "상표심사기준",
          partCount: 1,
          chapterCount: 1,
          itemCount: 0,
          supplementCount: 0,
        },
        parts: [
          {
            id: "front-matter",
            label: "전문",
            title: "전문",
            fullTitle: "전문",
            chapters: [
              {
                id: "전문-범례",
                label: "범례",
                title: "범례",
                fullTitle: "범례",
                pageLabel: null,
                items: [],
                supplements: [],
              },
            ],
          },
        ],
      },
      documentData: {
        meta: {
          title: "상표심사기준",
          builtAt: "2026-04-13T00:00:00.000Z",
          chapterCount: 1,
          pageCount: 575,
          partCount: 1,
        },
        chapters: [
          {
            id: "전문-범례",
            slug: "전문-범례",
            title: "범례",
            summary: "약어 설명",
            html: '<section id="overview"><h2>범례</h2><p>약어 설명</p></section>',
            hasImage: false,
            imageCount: 0,
            headings: [],
            partTitle: "전문",
            pageLabel: null,
            pageStart: 5,
            pageEnd: 5,
          },
        ],
      },
      searchIndex: [
        {
          id: "전문-범례-overview",
          chapterSlug: "전문-범례",
          chapterTitle: "범례",
          sectionId: "overview",
          sectionTitle: "개요",
          text: "약어 설명",
          excerpt: "약어 설명",
          entryType: "overview",
          partTitle: "전문",
          pageLabel: null,
          pageStart: 5,
          pageEnd: 5,
          hasImage: false,
          imageCount: 0,
          categories: [],
        },
      ],
      explorationIndex: [],
    });

    const chapter = data.chapterMap.get("전문-범례");
    expect(chapter?.pageLabel).toBeNull();
    expect(chapter?.sectionCatalog[0]?.pageLabel).toBeNull();
    expect(resolveCanonicalChapterRoute(chapter!, undefined).canonicalPath).toBe("/chapter/%EC%A0%84%EB%AC%B8-%EB%B2%94%EB%A1%80");
  });

  it("keeps search aliases searchable without adding them to the chapter outline and preserves bare chapter routes", () => {
    const data = adaptGeneratedData({
      manifest: {
        title: "상표심사기준",
        syncedAt: "2026-04-13T00:00:00.000Z",
        fileCount: 5,
        imageFileCount: 0,
      },
      toc: {
        meta: {
          title: "상표심사기준",
          partCount: 1,
          chapterCount: 1,
          itemCount: 1,
          supplementCount: 0,
        },
        parts: [
          {
            id: "part-1",
            label: "제1부",
            title: "총 칙",
            fullTitle: "제1부 총 칙",
            chapters: [
              {
                id: "chapter-1",
                label: "제1장",
                title: "제1장 목적",
                fullTitle: "제1장 목적",
                pageLabel: "10101",
                items: [{ id: "section-1" }],
                supplements: [],
              },
            ],
          },
        ],
      },
      documentData: {
        meta: {
          title: "상표심사기준",
          builtAt: "2026-04-13T00:00:00.000Z",
          chapterCount: 1,
          pageCount: 30,
          partCount: 1,
        },
        chapters: [
          {
            id: "chapter-1",
            slug: "chapter-1",
            title: "제1장 목적",
            summary: "목적 요약",
            html: '<section id="part-cover"><p>총칙 표지</p></section><section id="overview"><h2>제1장 목적</h2></section><section id="section-1"><h3>1. 심사기준의 목적</h3></section>',
            hasImage: true,
            imageCount: 1,
            headings: [{ id: "section-1", depth: 3, title: "1. 심사기준의 목적" }],
            partTitle: "제1부 총 칙",
            pageLabel: "10101",
            pageStart: 25,
            pageEnd: 26,
          },
        ],
      },
      searchIndex: [
        {
          id: "chapter-1-part-cover",
          chapterSlug: "chapter-1",
          chapterTitle: "제1장 목적",
          sectionId: "part-cover",
          sectionTitle: "총칙",
          text: "제1부 총 칙",
          excerpt: "총칙 표지",
          entryType: "part-cover",
          partTitle: "제1부 총 칙",
          pageLabel: null,
          pageStart: 23,
          pageEnd: 23,
          hasImage: true,
          imageCount: 1,
          categories: [],
        },
        {
          id: "chapter-1-overview",
          chapterSlug: "chapter-1",
          chapterTitle: "제1장 목적",
          sectionId: "overview",
          sectionTitle: "개요",
          text: "목적 요약",
          excerpt: "목적 요약",
          entryType: "overview",
          partTitle: "제1부 총 칙",
          pageLabel: "10101",
          pageStart: 25,
          pageEnd: 25,
          hasImage: false,
          imageCount: 0,
          categories: [],
        },
        {
          id: "section-1",
          chapterSlug: "chapter-1",
          chapterTitle: "제1장 목적",
          sectionId: "section-1",
          sectionTitle: "1. 심사기준의 목적",
          text: "상표법의 목적",
          excerpt: "상표법의 목적",
          entryType: "item",
          partTitle: "제1부 총 칙",
          pageLabel: "10101",
          pageStart: 25,
          pageEnd: 26,
          hasImage: false,
          imageCount: 0,
          categories: [],
        },
        {
          id: "chapter-1-alias-23",
          chapterSlug: "chapter-1",
          chapterTitle: "제1장 목적",
          sectionId: "overview",
          sectionTitle: "제1부 총칙",
          text: "제1부 총칙",
          excerpt: "제1부 총칙",
          entryType: "search-alias",
          partTitle: "제1부 총 칙",
          pageLabel: null,
          pageStart: 23,
          pageEnd: 23,
          hasImage: false,
          imageCount: 0,
          categories: ["supplement"],
        },
      ],
      explorationIndex: [],
    });

    const chapter = data.chapterMap.get("chapter-1");

    expect(chapter?.sectionCatalog.map((entry) => entry.sectionId)).toEqual(["part-cover", "overview", "section-1"]);
    expect(data.searchEntries.some((entry) => entry.entryType === "search-alias")).toBe(true);
    expect(chapter?.sectionCatalog.some((entry) => entry.entryType === "search-alias")).toBe(false);
    expect(resolveCanonicalChapterRoute(chapter!, undefined).canonicalPath).toBe("/chapter/chapter-1");
    expect(resolveCanonicalChapterRoute(chapter!, "part-cover").canonicalPath).toBe("/chapter/chapter-1/part-cover");
  });
});
