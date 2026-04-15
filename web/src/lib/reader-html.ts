const TABLE_OPEN_RE = /<table\b([^>]*)>/g;
const TABLE_CLOSE_RE = /<\/table>/g;
const LEADING_HEADING_PARAGRAPH_RE = /(<section\b[^>]*>\s*<(h2|h3)>(.*?)<\/\2>\s*<p>)([\s\S]*?)(<\/p>)/g;

function stripRepeatedHeadingLead(html: string): string {
  return html.replace(LEADING_HEADING_PARAGRAPH_RE, (match, prefix, _tag, title, paragraph, suffix) => {
    const heading = String(title ?? "").trim();
    const paragraphText = String(paragraph ?? "");
    if (!heading) {
      return match;
    }

    if (paragraphText.startsWith(`${heading} `)) {
      return `${prefix}${paragraphText.slice(heading.length + 1)}${suffix}`;
    }

    const headingIndex = paragraphText.indexOf(heading);
    const prefixText = headingIndex > 0 ? paragraphText.slice(0, headingIndex) : "";
    if (
      headingIndex > 0 &&
      headingIndex <= 80 &&
      !/[.!?:]\s*$/.test(prefixText) &&
      !/[.!?:]/.test(prefixText)
    ) {
      const afterHeading = paragraphText.slice(headingIndex + heading.length).trimStart();
      return `${prefix}${afterHeading}${suffix}`;
    }

    return match;
  });
}

export function enhanceReaderHtml(html: string): string {
  if (!html) {
    return html;
  }

  return stripRepeatedHeadingLead(html)
    .replace(TABLE_OPEN_RE, '<div class="reader-table-scroll"><table$1>')
    .replace(TABLE_CLOSE_RE, "</table></div>");
}
