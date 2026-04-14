import { describe, expect, it } from "vitest";

import { parsePartIntroText, stripPartIntroSection } from "../lib/part-intro";

describe("part intro helpers", () => {
  it("parses synthetic part intro text into description and list items", () => {
    expect(
      parsePartIntroText("이 편은 다음 장으로 구성됩니다. 제1장 의의 (p.3) / 제2장 심판의 법적 성질 (p.4)")
    ).toEqual({
      description: "이 편은 다음 장으로 구성됩니다.",
      items: ["제1장 의의 (p.3)", "제2장 심판의 법적 성질 (p.4)"],
    });
  });

  it("removes part-intro sections from chapter html", () => {
    expect(
      stripPartIntroSection(
        '<section id="overview"><p>overview</p></section><section id="part-intro"><p>intro</p></section><section id="body"><p>body</p></section>'
      )
    ).toBe('<section id="overview"><p>overview</p></section><section id="body"><p>body</p></section>');
  });
});
