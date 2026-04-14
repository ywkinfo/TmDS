const PART_INTRO_PREFIX = "이 편은 다음 장으로 구성됩니다.";
const PART_INTRO_SECTION_RE = /<section id="part-intro">[\s\S]*?<\/section>/i;

export type PartIntroContent = {
  description: string;
  items: string[];
};

export function parsePartIntroText(text: string): PartIntroContent {
  const trimmed = text.trim();
  if (!trimmed) {
    return { description: "", items: [] };
  }

  if (!trimmed.startsWith(PART_INTRO_PREFIX)) {
    return { description: trimmed, items: [] };
  }

  const remainder = trimmed.slice(PART_INTRO_PREFIX.length).trim();
  const items = remainder
    .split(" / ")
    .map((item) => item.trim())
    .filter(Boolean);

  return {
    description: PART_INTRO_PREFIX,
    items,
  };
}

export function stripPartIntroSection(html: string): string {
  if (!html) {
    return html;
  }

  return html.replace(PART_INTRO_SECTION_RE, "");
}
