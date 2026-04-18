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


def _extract_html_between_markers(chapter_html: str, start_marker: str, end_marker: str) -> str:
    _, _, remainder = chapter_html.partition(start_marker)
    assert remainder
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


def test_trim_leading_heading_noise_handles_compact_appendix_titles() -> None:
    cleaned = trim_leading_heading_noise(
        "부록3. 2006년 특허법․ 실용신안법 개정내용",
        "3. 2006년 특허법 실용신안법 개정내용",
        "부 록",
    )

    assert cleaned == ""


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
    assert 'class="reader-figure-scroll"' in front_notes["html"]


def test_first_chapter_document_html_excludes_fragmented_part_headers() -> None:
    document_data = load_generated_json("document-data.json")
    chapter = next(chapter for chapter in document_data["chapters"] if chapter["slug"] == "제1장-의의")

    assert "<p>제</p>" not in chapter["html"]
    assert "<p>1</p>" not in chapter["html"]
    assert "<p>편</p>" not in chapter["html"]


def test_first_chapter_document_html_repairs_broken_korean_spacing() -> None:
    document_data = load_generated_json("document-data.json")
    chapter = next(chapter for chapter in document_data["chapters"] if chapter["slug"] == "제1장-의의")

    assert "산업재산권은 전문적인 기술내용" in chapter["html"]
    assert "산업재 산권" not in chapter["html"]
    assert "행정심판· 소송" in chapter["html"]
    assert "행정 심판" not in chapter["html"]


def test_appendix_chapter_document_html_drops_duplicate_leading_title_line() -> None:
    document_data = load_generated_json("document-data.json")
    chapter = next(
        chapter
        for chapter in document_data["chapters"]
        if chapter["slug"] == "3-2006년-특허법-실용신안법-개정내용"
    )

    assert "<p>부록3. 2006년 특허법․ 실용신안법 개정내용</p>" not in chapter["html"]


def test_appendix_part_intro_generates_revision_history_search_alias() -> None:
    search_index = load_generated_json("search-index.json")
    alias = next(
        entry
        for entry in search_index
        if entry["entryType"] == "search-alias"
        and entry["chapterSlug"] == "1-심판관계서식례-및-기재례"
        and entry["sectionId"] == "part-intro"
    )

    assert alias["sectionTitle"] == "개정 연혁"
    assert "개정 연혁" in alias["text"]
    assert alias["categories"] == ["appendix"]


def test_chapter_overview_html_does_not_repeat_title_from_summary_fallback() -> None:
    document_data = load_generated_json("document-data.json")
    chapter = next(
        chapter
        for chapter in document_data["chapters"]
        if chapter["slug"] == "제2장-기간의-계산"
    )

    assert '<section id="overview"><h2>제2장 기간의 계산</h2><p>제2장 기간의 계산 ' not in chapter["html"]
    assert '<section id="제1절-기간의-종류"><h3>제1절 기간의 종류</h3>' in chapter["html"]


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


def test_boxed_callout_heading_is_preserved_as_inline_heading_markup() -> None:
    document_data = load_generated_json("document-data.json")
    chapter = next(
        chapter
        for chapter in document_data["chapters"]
        if chapter["slug"] == "제8장-특허무효심판-청구에-대한-심리"
    )

    assert '<h4 class="reader-inline-heading">【기재례】</h4>' in chapter["html"]
    assert '<p>【기재례】</p>' not in chapter["html"]


def test_angle_bracket_heading_is_preserved_as_inline_heading_markup() -> None:
    document_data = load_generated_json("document-data.json")
    chapter = next(
        chapter
        for chapter in document_data["chapters"]
        if chapter["slug"] == "제1장-심판의-주체"
    )

    assert '<h4 class="reader-inline-heading">&lt; 심판원장의 직무와 권한&gt;</h4>' in chapter["html"]
    assert '<p>&lt; 심판원장의 직무와 권한&gt;</p>' not in chapter["html"]


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


def test_table_crop_absorbs_wrapped_table_rows_without_text_leak() -> None:
    document_data = load_generated_json("document-data.json")
    chapter = next(chapter for chapter in document_data["chapters"] if chapter["slug"] == "제2장-기간의-계산")
    section_html = _extract_section_html(chapter["html"], "제1절-기간의-종류", "제2절-법정기간")

    assert "./generated/images/table-crops/0531-1.png" in section_html
    assert "<p>거절이유통지에 대한 의견서제출시, | 디자인일부심사에 대한 이의신청 답 | 변서 제출시, 무효심판에 대한 답변 | 서 제출시</p>" not in section_html


def test_table_crop_absorbs_narrow_intermediate_form_rows_without_split() -> None:
    document_data = load_generated_json("document-data.json")
    chapter = next(chapter for chapter in document_data["chapters"] if chapter["slug"] == "제1장-구술심리")
    section_html = _extract_section_html(chapter["html"], "제4절-구술심리기일의-종결", "제5절-심리종결과-재개")

    assert "./generated/images/table-crops/0403-1.png" in section_html
    assert "./generated/images/table-crops/0403-2.png" not in section_html
    assert "<p>000</p>" not in section_html
    assert "<p>특 허 심 판 원</p>" not in section_html
    assert "<p>제 oo 부</p>" not in section_html
    assert "<p>구 술 심 리 조 서</p>" not in section_html


def test_table_crop_absorbs_single_column_intermediate_rows_within_same_table() -> None:
    document_data = load_generated_json("document-data.json")
    chapter = next(chapter for chapter in document_data["chapters"] if chapter["slug"] == "제3장-심결분류")
    section_html = _extract_section_html(chapter["html"], "제3절-심결분류표", "제4절-심결분류-및-판결분류의-사용요령")

    assert "./generated/images/table-crops/0468-1.png" in section_html
    assert "<p>조약위반의 출원</p>" not in section_html
    assert "<p>조약위반의 등록</p>" not in section_html
    assert "<p>등록후의 조약위반</p>" not in section_html
    assert "<p>610</p>" not in section_html
    assert "<p>620</p>" not in section_html


def test_appendix_form_pages_render_as_single_crop_without_field_label_leak() -> None:
    document_data = load_generated_json("document-data.json")
    chapter = next(
        chapter
        for chapter in document_data["chapters"]
        if chapter["slug"] == "1-심판관계서식례-및-기재례"
    )
    html = chapter["html"]
    appendix_6_1_html = _extract_html_between_markers(
        html,
        "./generated/images/table-crops/1236-1.png",
        "./generated/images/table-crops/1237-1.png",
    )
    appendix_6_2_html = _extract_html_between_markers(
        html,
        "./generated/images/table-crops/1237-1.png",
        "./generated/images/table-crops/1238-1.png",
    )
    appendix_6_3_html = _extract_html_between_markers(
        html,
        "./generated/images/table-crops/1238-1.png",
        "./generated/images/table-crops/1239-1.png",
    )
    appendix_6_4_html = _extract_html_between_markers(
        html,
        "./generated/images/table-crops/1239-1.png",
        "./generated/images/table-crops/1240-1.png",
    )
    appendix_6_5_html = _extract_html_between_markers(
        html,
        "./generated/images/table-crops/1240-1.png",
        "./generated/images/table-crops/1241-1.png",
    )

    assert "./generated/images/table-crops/1239-1.png" in html
    assert "./generated/images/table-crops/1239-2.png" not in html
    assert "./generated/images/table-crops/1240-1.png" in html
    assert "./generated/images/table-crops/1240-2.png" not in html
    assert "<p>위 사실을 증명함.</p>" not in appendix_6_1_html
    assert "<p>20 . . .</p>" not in appendix_6_1_html
    assert "<p>특 허 심 판 원 장 삎</p>" not in appendix_6_1_html
    assert "<p>위 사실을 증명함.</p>" not in appendix_6_2_html
    assert "<p>20 . . .</p>" not in appendix_6_2_html
    assert "<p>특 허 심 판 원 장 삎</p>" not in appendix_6_2_html
    assert "<p>위 사실을 증명함.</p>" not in appendix_6_3_html
    assert "<p>20 . . .</p>" not in appendix_6_3_html
    assert "<p>특 허 심 판 원 장 삎</p>" not in appendix_6_3_html
    assert "<p>청 구 인</p>" not in appendix_6_4_html
    assert "<p>피 청 구 인</p>" not in appendix_6_4_html
    assert "<p>위 사실을 증명함.</p>" not in appendix_6_4_html
    assert "<p>청 구 인</p>" not in appendix_6_5_html
    assert "<p>피청구인</p>" not in appendix_6_5_html
    assert "<p>위 사실을 증명함.</p>" not in appendix_6_5_html
    assert "<p>특 허 심 판 원 심 판 정 책 과 장 삎</p>" not in appendix_6_5_html


def test_comparison_table_page_absorbs_wrapped_single_column_rows() -> None:
    document_data = load_generated_json("document-data.json")
    chapter = next(
        chapter
        for chapter in document_data["chapters"]
        if chapter["slug"] == "제5장-정정-인정여부-판단-유형-및-사례"
    )
    table_window = _extract_html_between_markers(
        chapter["html"],
        "./generated/images/table-crops/0814-1.png",
        "./generated/images/table-crops/0815-1.png",
    )

    assert "./generated/images/table-crops/0814-1.png" in chapter["html"]
    assert "./generated/images/table-crops/0814-2.png" not in chapter["html"]
    assert "./generated/images/table-crops/0814-3.png" not in chapter["html"]
    assert "<p>하여 확장이나 변경에 해당하는지 여부를 판단)</p>" not in table_window
    assert "<p>해당)</p>" not in table_window
    assert "<p>위의 실질적인 변경에 해당되지 아니한다)</p>" not in table_window
