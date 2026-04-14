import type { ReaderChapter, ReaderSectionEntry } from "./generated-data";
import { normalizeText } from "./formatters";

export type WarmedSearchEntry = ReaderSectionEntry & {
  normalizedPartTitle: string;
  normalizedSectionTitle: string;
  normalizedChapterTitle: string;
  normalizedExcerpt: string;
  normalizedText: string;
  normalizedHaystack: string;
};

export type SearchWarmStatus = "ready" | "empty";

export function warmSearchEntries(entries: ReaderSectionEntry[]): WarmedSearchEntry[] {
  return entries.map((entry) => ({
    ...entry,
    normalizedPartTitle: normalizeText(entry.partTitle),
    normalizedSectionTitle: normalizeText(entry.sectionTitle),
    normalizedChapterTitle: normalizeText(entry.chapterTitle),
    normalizedExcerpt: normalizeText(entry.excerpt),
    normalizedText: normalizeText(entry.text),
    normalizedHaystack: normalizeText(
      `${entry.sectionTitle} ${entry.chapterTitle} ${entry.partTitle} ${entry.excerpt} ${entry.text}`
    ),
  }));
}

export function buildWarmedSearchState(entries: ReaderSectionEntry[]): {
  status: SearchWarmStatus;
  entries: WarmedSearchEntry[];
} {
  const warmedEntries = warmSearchEntries(entries);

  return {
    status: warmedEntries.length > 0 ? "ready" : "empty",
    entries: warmedEntries,
  };
}

function scoreFieldMatch(
  haystack: string,
  normalizedQuery: string,
  scoreMap: { exact: number; startsWith: number; includes: number }
): number {
  if (!haystack || !normalizedQuery) {
    return 0;
  }
  if (haystack === normalizedQuery) {
    return scoreMap.exact;
  }
  if (haystack.startsWith(normalizedQuery)) {
    return scoreMap.startsWith;
  }
  if (haystack.includes(normalizedQuery)) {
    return scoreMap.includes;
  }
  return 0;
}

export function rankSearchResults(entries: WarmedSearchEntry[], query: string, limit = 10): WarmedSearchEntry[] {
  const normalizedQuery = normalizeText(query);
  if (!normalizedQuery) {
    return [];
  }

  return entries
    .map((entry) => {
      let score = 0;

      score += scoreFieldMatch(entry.normalizedSectionTitle, normalizedQuery, {
        exact: 120,
        startsWith: 90,
        includes: 60,
      });
      score += scoreFieldMatch(entry.normalizedChapterTitle, normalizedQuery, {
        exact: 100,
        startsWith: 75,
        includes: 48,
      });
      score += scoreFieldMatch(entry.normalizedPartTitle, normalizedQuery, {
        exact: 72,
        startsWith: 48,
        includes: 30,
      });
      score += scoreFieldMatch(entry.normalizedExcerpt, normalizedQuery, {
        exact: 24,
        startsWith: 14,
        includes: 8,
      });
      score += scoreFieldMatch(entry.normalizedText, normalizedQuery, {
        exact: 18,
        startsWith: 10,
        includes: 6,
      });

      return score > 0 ? { entry, score } : null;
    })
    .filter((value): value is { entry: WarmedSearchEntry; score: number } => value !== null)
    .sort((left, right) => {
      if (right.score !== left.score) {
        return right.score - left.score;
      }

      const leftSpan = (left.entry.pageEnd ?? left.entry.pageStart ?? 0) - (left.entry.pageStart ?? 0);
      const rightSpan = (right.entry.pageEnd ?? right.entry.pageStart ?? 0) - (right.entry.pageStart ?? 0);
      if (leftSpan !== rightSpan) {
        return leftSpan - rightSpan;
      }

      return (left.entry.pageStart ?? 0) - (right.entry.pageStart ?? 0);
    })
    .slice(0, limit)
    .map(({ entry }) => entry);
}

export function resolveSearchNavigation(input: {
  query: string;
  results: Array<Pick<ReaderSectionEntry, "routePath">>;
  activeIndex: number;
  chapters: ReaderChapter[];
}): string | null {
  const normalizedQuery = normalizeText(input.query);
  if (!normalizedQuery) {
    return null;
  }

  const selectedResult = input.results[input.activeIndex];
  if (selectedResult) {
    return selectedResult.routePath;
  }

  if (input.results[0]) {
    return input.results[0].routePath;
  }

  const chapterScores = input.chapters
    .map((chapter) => {
      const normalizedChapterTitle = normalizeText(chapter.displayTitle);
      const normalizedPartTitle = normalizeText(chapter.partTitle);
      const score =
        scoreFieldMatch(normalizedChapterTitle, normalizedQuery, {
          exact: 120,
          startsWith: 90,
          includes: 60,
        }) +
        scoreFieldMatch(normalizedPartTitle, normalizedQuery, {
          exact: 80,
          startsWith: 56,
          includes: 32,
        });

      return score > 0 ? { chapter, score } : null;
    })
    .filter((value): value is { chapter: ReaderChapter; score: number } => value !== null)
    .sort((left, right) => {
      if (right.score !== left.score) {
        return right.score - left.score;
      }
      return (left.chapter.pageStart ?? 0) - (right.chapter.pageStart ?? 0);
    });

  return chapterScores[0]?.chapter.sectionCatalog[0]?.routePath ?? null;
}
