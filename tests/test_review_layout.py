from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pipeline import build_inventory
from pipeline.common import load_config, load_generated_json, open_pdf
from pipeline.review_layout import (
    PAGE_LAYOUT_DECORATIVE,
    PAGE_LAYOUT_LIST,
    PAGE_LAYOUT_PROSE,
    PAGE_LAYOUT_TABLE,
    PAGE_LAYOUT_TOC,
    RUNNING_HEADER_PATTERNS,
    build_page_review_entries,
    load_paragraph_overrides,
)


@lru_cache(maxsize=1)
def _load_review_entries() -> list[dict[str, object]]:
    inventory_path = Path(__file__).resolve().parents[1] / "data" / "generated" / "pdf-inventory.json"
    if not inventory_path.exists():
        build_inventory.main()

    config = load_config()
    inventory = load_generated_json("pdf-inventory.json")
    document = open_pdf(config)
    return build_page_review_entries(document, inventory)


@lru_cache(maxsize=1)
def _entry_by_page() -> dict[int, dict[str, object]]:
    return {int(entry["pageNumber"]): entry for entry in _load_review_entries()}


@lru_cache(maxsize=1)
def _page_meta_by_page() -> dict[int, dict[str, object]]:
    inventory = load_generated_json("pdf-inventory.json")
    return {int(page["pageNumber"]): page for page in inventory.get("pages", [])}


def test_preface_page_5_matches_gold_standard_paragraphs() -> None:
    page5 = _entry_by_page()[5]
    paragraphs = page5["paragraphs"]

    assert page5["pageLayoutKind"] == PAGE_LAYOUT_PROSE
    assert page5["hasOverride"] is False
    assert page5["confidence"] == "high"
    assert page5["paragraphCount"] == 10
    assert paragraphs[0]["text"] == "머 리 말"
    assert paragraphs[1]["text"].startswith("최근 급격한 기술 변화와 함께 기술 경쟁이 날로 치열해지고")
    assert paragraphs[7]["text"].startswith("끝으로 심판편람을 수정, 보완하여 발간하기까지")
    assert paragraphs[8]["text"] == "2023년 12월 29일"
    assert paragraphs[8]["kind"] == "date"
    assert paragraphs[9]["text"] == "특허심판원장 박 종 주"
    assert paragraphs[9]["kind"] == "signature"


def test_page_8_is_classified_as_list_and_keeps_entry_boundaries() -> None:
    page8 = _entry_by_page()[8]
    paragraphs = page8["paragraphs"]

    assert page8["pageLayoutKind"] == PAGE_LAYOUT_LIST
    assert page8["paragraphCount"] == 30
    assert paragraphs[0]["text"] == "8. 약칭은 다음과 같이 하였다."
    assert paragraphs[1]["text"].startswith("§○○")
    assert paragraphs[-1]["text"].startswith("9. 대법원 판례번호의 사건 구분은 다음과 같다.")
    assert "http://www.scourt.go.kr" in paragraphs[-1]["text"]


def test_page_7_splits_explanatory_note_out_of_list_rows() -> None:
    page7 = _entry_by_page()[7]
    paragraphs = page7["paragraphs"]

    assert page7["pageLayoutKind"] == PAGE_LAYOUT_LIST
    assert page7["hasOverride"] is True
    assert paragraphs[-2]["text"].startswith("가), 나), 다)")
    assert paragraphs[-1]["text"].startswith("다시 항을 나누는 의미가 아니고")


def test_page_20_is_classified_as_toc_without_running_header_fragments() -> None:
    page20 = _entry_by_page()[20]
    paragraphs = page20["paragraphs"]

    assert page20["pageLayoutKind"] == PAGE_LAYOUT_TOC
    assert page20["paragraphCount"] >= 30
    assert paragraphs[0]["text"].startswith("제6장 권리범위 확인심판의 심결")
    assert all(paragraph["text"] != "심판편람(제14판)" for paragraph in paragraphs)


def test_page_31_drops_right_margin_part_header_fragments_from_body() -> None:
    page31 = _entry_by_page()[31]
    paragraphs = page31["paragraphs"]
    texts = [paragraph["text"] for paragraph in paragraphs]

    assert page31["pageLayoutKind"] == PAGE_LAYOUT_PROSE
    assert "제" not in texts
    assert "1" not in texts
    assert "편" not in texts
    assert paragraphs[2]["text"].startswith("특허심판이란 특허· 실용신안· 디자인· 상표 출원에 대하여")
    assert "분에 의해 등록된 산업재산권의 효력의 유효 여부" in paragraphs[2]["text"]
    assert paragraphs[2]["text"].endswith("특별행정심판제도를 말한다.")


def test_page_9_is_classified_as_table_form_and_emits_row_items() -> None:
    page9 = _entry_by_page()[9]
    paragraphs = page9["paragraphs"]

    assert page9["pageLayoutKind"] == PAGE_LAYOUT_TABLE
    assert page9["paragraphCount"] >= 20
    assert " | " in paragraphs[0]["text"]
    assert paragraphs[1]["boundaryReason"] == "table-row"
    assert paragraphs[1]["text"].startswith("002 | 가합 | 민사 | 민사1심합의사건")
    assert "068 | 준재가소 | 민사 | 민사소액사건준재심" in paragraphs[1]["text"]


def test_page_603_drops_vertical_part_header_fragments_for_split_part_titles() -> None:
    page603 = _entry_by_page()[603]
    texts = [paragraph["text"] for paragraph in page603["paragraphs"]]

    assert page603["pageLayoutKind"] == PAGE_LAYOUT_PROSE
    assert "제" not in texts
    assert "편" not in texts
    assert "14 -1" not in texts


def test_page_29_is_classified_as_decorative_structural() -> None:
    page29 = _entry_by_page()[29]

    assert page29["pageLayoutKind"] == PAGE_LAYOUT_DECORATIVE
    assert page29["paragraphCount"] == 5
    assert [paragraph["text"] for paragraph in page29["paragraphs"]] == [
        "제1편",
        "특허심판 일반",
        "제1장 의의",
        "제2장 심판의 법적 성질",
        "제3장 특허심판의 종류",
    ]


def test_page_50_remains_prose_with_headings_and_body_blocks() -> None:
    page50 = _entry_by_page()[50]
    paragraphs = page50["paragraphs"]

    assert page50["pageLayoutKind"] == PAGE_LAYOUT_PROSE
    assert page50["hasOverride"] is False
    assert paragraphs[0]["text"] == "2. 심결 등본 송달"
    assert paragraphs[0]["kind"] == "heading"
    assert paragraphs[1]["text"] == "가. 특별우편송달"
    assert paragraphs[1]["kind"] == "heading"
    assert paragraphs[2]["text"].startswith("심판장은 심결 또는 결정이 있는 때에는")
    assert paragraphs[3]["text"] == "나. 정보통신망에 의한 송달"


def test_page_86_splits_boxed_case_heading_into_its_own_paragraph() -> None:
    page86 = _entry_by_page()[86]
    paragraphs = page86["paragraphs"]
    texts = [paragraph["text"] for paragraph in paragraphs]

    heading_index = texts.index("【청구이유 기재 정도에 판례】")
    assert paragraphs[heading_index]["kind"] == "heading"
    assert "【청구이유 기재 정도에 판례】" not in paragraphs[heading_index - 1]["text"]


def test_page_96_splits_angle_bracket_heading_into_its_own_paragraph() -> None:
    page96 = _entry_by_page()[96]
    paragraphs = page96["paragraphs"]
    texts = [paragraph["text"] for paragraph in paragraphs]

    heading_index = texts.index("< 심판장 및 심판관의 직무와 권한>")
    assert paragraphs[heading_index]["kind"] == "heading"
    assert "< 심판장 및 심판관의 직무와 권한>" not in paragraphs[heading_index - 1]["text"]
    assert paragraphs[heading_index + 1]["text"].startswith("심판장 및 심판관은 다음 사항을 분장한다.")


def test_page_1256_strips_appendix_running_header_from_first_paragraph() -> None:
    page1256 = _entry_by_page()[1256]
    first_text = page1256["paragraphs"][0]["text"]

    assert not first_text.startswith("부 록")


def test_prose_pages_have_non_empty_paragraphs_without_running_header_residue() -> None:
    inventory = _page_meta_by_page()
    prose_entries = [
        entry
        for entry in _load_review_entries()
        if entry["pageLayoutKind"] == PAGE_LAYOUT_PROSE and inventory[int(entry["pageNumber"])].get("hasText")
    ]

    assert prose_entries

    for entry in prose_entries:
        assert int(entry["paragraphCount"]) > 0
        body_lengths = [len(paragraph["text"]) for paragraph in entry["paragraphs"] if paragraph["kind"] == "body"]
        if body_lengths:
            assert max(body_lengths) <= 900
        first_text = entry["paragraphs"][0]["text"]
        assert not any(pattern.match(first_text) for pattern in RUNNING_HEADER_PATTERNS)


def test_overrides_file_no_longer_pins_preface_page() -> None:
    overrides = load_paragraph_overrides()
    assert 5 not in overrides
