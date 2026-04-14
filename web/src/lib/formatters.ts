export const CATEGORY_LABELS: Record<string, string> = {
  "related-law": "관련 법령",
  party: "주체",
  requirements: "적용 요건",
  caution: "유의사항",
  timing: "판단 시점",
  evidence: "증거",
  criteria: "판단 기준",
  case: "사례·예시",
  supplement: "보충자료",
  procedure: "절차",
  appendix: "부록",
};

export function stripGuideDots(value: string | null | undefined): string {
  return String(value ?? "")
    .replace(/[·․]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

export function normalizeText(value: string | null | undefined): string {
  return stripGuideDots(value).replace(/\s+/g, "").toLowerCase();
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) {
    return "미상";
  }

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat("ko-KR", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(parsed);
}

export function compactSummary(value: string | null | undefined, maxLength = 120): string {
  const text = stripGuideDots(value);
  if (!text) {
    return "";
  }

  if (text.length <= maxLength) {
    return text;
  }

  const sentenceBreak = text.search(/[.!?]\s|다\.\s|요\.\s/);
  if (sentenceBreak > 0 && sentenceBreak + 1 <= maxLength) {
    return text.slice(0, sentenceBreak + 1).trim();
  }

  const clipped = text.slice(0, maxLength);
  const lastSpace = clipped.lastIndexOf(" ");
  const safe = lastSpace >= maxLength * 0.6 ? clipped.slice(0, lastSpace) : clipped;
  return safe.trimEnd() + "…";
}

export function formatPageRange(
  start: number | null | undefined,
  end: number | null | undefined,
  labelStart?: string | null,
  labelEnd?: string | null
): string {
  if (labelStart || labelEnd) {
    if (!labelEnd || labelStart === labelEnd) {
      return `p.${labelStart ?? labelEnd}`;
    }

    return `p.${labelStart}-${labelEnd}`;
  }

  if (!start && !end) {
    return "페이지 미상";
  }

  if (!end || start === end) {
    return `PDF ${start}`;
  }

  return `PDF ${start}-${end}`;
}

export function getCategoryLabel(category: string): string {
  return CATEGORY_LABELS[category] ?? category;
}

export function buildChapterPath(chapterSlug: string): string {
  return `/chapter/${encodeURIComponent(chapterSlug)}`;
}

export function buildSectionPath(chapterSlug: string, sectionId: string): string {
  if (!sectionId || sectionId === "overview") {
    return buildChapterPath(chapterSlug);
  }

  return `${buildChapterPath(chapterSlug)}/${encodeURIComponent(sectionId)}`;
}

export function buildCompositeKey(input: {
  partTitle: string;
  chapterTitle: string;
  pageLabel: string | null | undefined;
  pageStart: number | null | undefined;
  pageEnd: number | null | undefined;
  title: string;
}): string {
  return [
    normalizeText(input.partTitle),
    normalizeText(input.chapterTitle),
    String(input.pageLabel ?? ""),
    String(input.pageStart ?? ""),
    String(input.pageEnd ?? ""),
    normalizeText(input.title),
  ].join("::");
}

export function buildChapterCompositeKey(input: {
  partTitle: string;
  chapterTitle: string;
  pageLabel: string | null | undefined;
}): string {
  return [normalizeText(input.partTitle), normalizeText(input.chapterTitle), String(input.pageLabel ?? "")].join(
    "::"
  );
}
