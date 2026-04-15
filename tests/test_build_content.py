from __future__ import annotations

from pipeline.build_content import (
    build_part_intro_content,
    classify_entry,
    split_table_cells,
    table_rows_to_html,
    trim_leading_heading_noise,
)
from pipeline.common import load_generated_json


def _extract_section_html(chapter_html: str, section_id: str, next_section_id: str | None = None) -> str:
    start_marker = f'<section id="{section_id}">'
    _, _, remainder = chapter_html.partition(start_marker)
    assert remainder
    if next_section_id is None:
        return remainder
    end_marker = f'<section id="{next_section_id}">'
    section_html, _, _ = remainder.partition(end_marker)
    return section_html


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


def test_table_rows_to_html_renders_synthetic_table_markup() -> None:
    rows = [
        split_table_cells("코드 | 사건 구분 | 사건 유형 | 내용"),
        split_table_cells("002 | 가합 | 민사 | 민사1심합의사건"),
    ]

    html = table_rows_to_html(rows)

    assert "<table" in html
    assert "<thead>" in html
    assert "<th>코드</th>" in html
    assert "<td>002</td>" in html
    assert "<td>민사1심합의사건</td>" in html


def test_front_notes_document_html_excludes_toc_spread() -> None:
    document_data = load_generated_json("document-data.json")
    front_notes = next(chapter for chapter in document_data["chapters"] if chapter["slug"] == "front-notes")

    assert "간략목차" not in front_notes["html"]
    assert "간 략 목 차" not in front_notes["html"]


def test_front_notes_document_html_renders_case_code_section_as_page_image() -> None:
    document_data = load_generated_json("document-data.json")
    front_notes = next(chapter for chapter in document_data["chapters"] if chapter["slug"] == "front-notes")

    assert "./generated/images/table-crops/0009-1.png" in front_notes["html"]


def test_first_chapter_document_html_excludes_fragmented_part_headers() -> None:
    document_data = load_generated_json("document-data.json")
    chapter = next(chapter for chapter in document_data["chapters"] if chapter["slug"] == "제1장-의의")

    assert "<p>제</p>" not in chapter["html"]
    assert "<p>1</p>" not in chapter["html"]
    assert "<p>편</p>" not in chapter["html"]


def test_same_page_sections_are_split_without_repeating_neighbor_content() -> None:
    document_data = load_generated_json("document-data.json")
    chapter = next(
        chapter
        for chapter in document_data["chapters"]
        if chapter["slug"] == "제2장-심판청구서-접수-후-절차-심판정책과"
    )

    section2_html = _extract_section_html(
        chapter["html"],
        "제2절-심판서류-처리",
        "제3절-심판처리부-기재",
    )
    section3_html = _extract_section_html(
        chapter["html"],
        "제3절-심판처리부-기재",
        "제4절-등록원부-예고등록의뢰",
    )
    section6_html = _extract_section_html(
        chapter["html"],
        "제6절-심판관-지정",
        "제7절-심판관지정-변경-통지서의-작성-및-통지",
    )
    section7_html = _extract_section_html(
        chapter["html"],
        "제7절-심판관지정-변경-통지서의-작성-및-통지",
        "제8절-방식심리",
    )

    assert "제1절 심판번호 부여" not in section2_html
    assert "온라인 심판청구 이후 심판서류철은 원칙적으로 작성하지 않으며" in section2_html
    assert "제3절 심판처리부 기재" not in section2_html
    assert "심판정책과는 특허넷에 다음 사항을 입력한다." in section3_html
    assert "제4절 등록원부 예고등록의뢰" not in section3_html
    assert "제7절 심판관지정" not in section6_html
    assert "심판번호 및 심판관지정의 결재가 있으면" in section7_html


def test_complex_table_pages_render_as_pdf_page_images() -> None:
    document_data = load_generated_json("document-data.json")
    chapter = next(chapter for chapter in document_data["chapters"] if chapter["slug"] == "제1장-의의-2")

    assert "./generated/images/table-crops/0064-1.png" in chapter["html"]
    assert "./generated/images/table-crops/0065-1.png" in chapter["html"]
    assert "<p>10. 제척․ 기피 결정에 대한 불복</p>" not in chapter["html"]
    assert "<p>11. 기타 부적법한 심판청구로 그 흠을 보정할</p>" not in chapter["html"]


def test_table_sections_keep_sandwiched_prose_pages_as_pdf_images() -> None:
    document_data = load_generated_json("document-data.json")
    chapter = next(chapter for chapter in document_data["chapters"] if chapter["slug"] == "제3장-심결분류")

    assert "./generated/images/table-crops/0461-1.png" in chapter["html"]
    assert "./generated/images/table-crops/0462-1.png" in chapter["html"]
    assert "./generated/images/table-crops/0463-1.png" in chapter["html"]
