import { describe, expect, it } from "vitest";

import { enhanceReaderHtml } from "../lib/reader-html";

describe("enhanceReaderHtml", () => {
  it("wraps generated tables in a horizontal scroll container", () => {
    const html = "<section id=\"overview\"><table><tbody><tr><td>A</td></tr></tbody></table></section>";

    const enhanced = enhanceReaderHtml(html);

    expect(enhanced).toContain('<div class="reader-table-scroll"><table>');
    expect(enhanced).toContain("</table></div>");
  });

  it("leaves non-table markup unchanged", () => {
    const html = "<section id=\"overview\"><p>text only</p></section>";

    expect(enhanceReaderHtml(html)).toBe(html);
  });

  it("removes a repeated section heading from the first paragraph", () => {
    const html =
      "<section id=\"overview\"><h2>제1장 의의</h2><p>제1장 의의 특허심판이란 특허· 실용신안· 디자인· 상표 출원에 대하여</p></section>";

    expect(enhanceReaderHtml(html)).toContain("<p>특허심판이란 특허· 실용신안· 디자인· 상표 출원에 대하여</p>");
  });

  it("removes leading part and chapter labels when the heading repeats near the front", () => {
    const html =
      "<section id=\"overview\"><h2>제1장 의의</h2><p>제1편 특허심판 일반 제1장 의의 특허심판이란 특허· 실용신안· 디자인· 상표 출원에 대하여</p></section>";

    expect(enhanceReaderHtml(html)).toContain("<p>특허심판이란 특허· 실용신안· 디자인· 상표 출원에 대하여</p>");
  });
});
