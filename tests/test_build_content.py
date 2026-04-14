from __future__ import annotations

from pipeline.build_content import build_part_intro_content, classify_entry, trim_leading_heading_noise


def test_classify_entry_assigns_procedure_and_party_categories() -> None:
    assert classify_entry({"sectionTitle": "제2절 참가의 신청 또는 취하", "partTitle": "제5편 심판의 당사자ㆍ대리인ㆍ참가인"}) == [
        "party",
        "procedure",
    ]


def test_classify_entry_assigns_evidence_and_case_categories() -> None:
    assert classify_entry({"sectionTitle": "제10장 증거조사 관련 판례", "partTitle": "제9편 증거조사"}) == [
        "evidence",
        "case",
    ]


def test_classify_entry_marks_appendix_content() -> None:
    assert "appendix" in classify_entry(
        {"sectionTitle": "3. 2006년 특허법 실용신안법 개정내용", "partTitle": "부 록"}
    )


def test_build_part_intro_content_lists_chapters_with_locators() -> None:
    html, text = build_part_intro_content(
        {
            "fullTitle": "제1편 특허심판 일반",
            "chapters": [
                {"fullTitle": "제1장 의의", "pageLabelStart": "3", "pageStart": 31},
                {"fullTitle": "제2장 심판의 법적 성질", "pageLabelStart": "4", "pageStart": 32},
            ],
        }
    )

    assert "이 편은 다음 장으로 구성됩니다." in text
    assert "제1장 의의 (p.3)" in text
    assert "제2장 심판의 법적 성질 (p.4)" in text
    assert "<p>제1장 의의 (p.3)</p>" in html


def test_trim_leading_heading_noise_removes_repeated_part_and_chapter_titles() -> None:
    cleaned = trim_leading_heading_noise(
        "제2장 심판청구서 접수 후 절차 (심판정책과) 제2편 심판서류의 접수 심판관지정 및 열람 제2장 심판청구서 접수 후 절차 (심판정책과) 심판청구서가 접수된 때는 심판정책과는 아래와 같은 절차를 밟는다.",
        "제2장 심판청구서 접수 후 절차 (심판정책과)",
        "제2편 심판서류의 접수 심판관지정 및 열람",
    )

    assert cleaned == "심판청구서가 접수된 때는 심판정책과는 아래와 같은 절차를 밟는다."
