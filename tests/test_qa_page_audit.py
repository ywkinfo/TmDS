from __future__ import annotations

from pipeline.qa_page_audit import (
    build_page_entry_overlap,
    build_report,
    classify_risk_tier,
    detect_page_flags,
)


def test_build_page_entry_overlap_counts_multi_section_pages_from_non_alias_entries() -> None:
    overlap = build_page_entry_overlap(
        [
            {"entryType": "item", "sectionId": "a", "pageStart": 10, "pageEnd": 10},
            {"entryType": "item", "sectionId": "b", "pageStart": 10, "pageEnd": 11},
            {"entryType": "overview", "sectionId": "overview", "pageStart": 10, "pageEnd": 10},
            {"entryType": "search-alias", "sectionId": "alias", "pageStart": 10, "pageEnd": 10},
        ]
    )

    assert overlap[10] == {"item::a", "item::b"}
    assert overlap[11] == {"item::b"}


def test_build_report_does_not_promote_overview_plus_single_item_to_multi_section() -> None:
    report = build_report(
        page_review=[
            {
                "pageNumber": 10,
                "pageLabel": None,
                "chapterSlug": "chapter-a",
                "sectionId": "section-a",
                "pageLayoutKind": "list",
                "confidence": "medium",
                "hasOverride": False,
                "mergeFirstGroupWithPreviousPage": False,
                "paragraphs": [],
            }
        ],
        search_index=[
            {"entryType": "overview", "sectionId": "overview", "pageStart": 10, "pageEnd": 10},
            {"entryType": "item", "sectionId": "section-a", "pageStart": 10, "pageEnd": 10},
        ],
        document_data={
            "chapters": [
                {
                    "slug": "chapter-a",
                    "html": "<section></section>",
                }
            ]
        },
    )

    page = report["pages"][0]
    assert page["sectionOverlapCount"] == 1
    assert "multi-section-page" not in page["flags"]
    assert page["riskTier"] == "low"


def test_detect_page_flags_marks_low_confidence_override_merge_and_crop_gaps() -> None:
    flags = detect_page_flags(
        {
            "pageNumber": 44,
            "pageLayoutKind": "table/form",
            "confidence": "low",
            "hasOverride": True,
            "mergeFirstGroupWithPreviousPage": True,
            "paragraphs": [{"text": "【사례】"}],
        },
        section_overlap_count=3,
        chapter_html="<section><p>no crop here</p></section>",
    )

    assert "multi-section-page" in flags
    assert "low-confidence" in flags
    assert "has-override" in flags
    assert "page-merge" in flags
    assert "boxed-heading" in flags
    assert "missing-table-crop" in flags


def test_detect_page_flags_ignores_angle_brackets_inside_table_rows() -> None:
    flags = detect_page_flags(
        {
            "pageNumber": 1262,
            "pageLayoutKind": "table/form",
            "confidence": "medium",
            "hasOverride": False,
            "mergeFirstGroupWithPreviousPage": False,
            "paragraphs": [
                {"text": "[ 이의신청ㆍ무효심판ㆍ새로운 무효심판사유의 대비]"},
                {"text": "<특허법 제69조 제1항> | <특허법 제133조 제1항> | <개정 특허법 제133조 제1항>"},
            ],
        },
        section_overlap_count=0,
        chapter_html='<section><img src="./generated/images/table-crops/1262-1.png" /></section>',
    )

    assert "boxed-heading" in flags
    assert "angle-heading" not in flags


def test_detect_page_flags_marks_korean_linebreak_residue() -> None:
    flags = detect_page_flags(
        {
            "pageNumber": 303,
            "pageLayoutKind": "prose",
            "confidence": "high",
            "hasOverride": False,
            "mergeFirstGroupWithPreviousPage": False,
            "paragraphs": [
                {"text": "※ 민사소송법 제341조(감정의 촉탁) ②제1항의 경우에 법원은 필요하다고 인정하면 공공기 관이 지정한 사람으로 하여금 감정서를 설명하 게 할 수 있다."}
            ],
        },
        section_overlap_count=0,
        chapter_html="<section><p>text only</p></section>",
    )

    assert "korean-linebreak-residue" in flags


def test_detect_page_flags_marks_split_statutory_reference_as_korean_linebreak_residue() -> None:
    flags = detect_page_flags(
        {
            "pageNumber": 307,
            "pageLayoutKind": "prose",
            "confidence": "high",
            "hasOverride": False,
            "mergeFirstGroupWithPreviousPage": False,
            "paragraphs": [
                {"text": "문서송부촉탁은 위 ③의 경우이며, 심판장은 제3자에게 문서의 송부를 촉탁할 수 있다(민소"},
                {"text": "§29413)). 심판장은 당사자가 특허심판원으로 하여금 문서제출의무를 부담하는 문서소지자에 대해 문서제출을 요구하도록 한다."},
            ],
        },
        section_overlap_count=0,
        chapter_html="<section><p>text only</p></section>",
    )

    assert "korean-linebreak-residue" in flags


def test_detect_page_flags_ignores_normal_korean_spacing() -> None:
    flags = detect_page_flags(
        {
            "pageNumber": 304,
            "pageLayoutKind": "prose",
            "confidence": "high",
            "hasOverride": False,
            "mergeFirstGroupWithPreviousPage": False,
            "paragraphs": [
                {"text": "그 밖의 단체 또는 외국 공공기관이 지정한 사람으로 하여금 감정서를 설명하게 할 수 있다."},
                {"text": "법원은 필요하다고 인정하면 당사자에게 의견을 제출하게 할 수 있다."},
            ],
        },
        section_overlap_count=0,
        chapter_html="<section><p>text only</p></section>",
    )

    assert "korean-linebreak-residue" not in flags


def test_classify_risk_tier_promotes_high_risk_signals() -> None:
    assert (
        classify_risk_tier({"pageLayoutKind": "table/form", "confidence": "medium"}, ["missing-table-crop"])
        == "high"
    )
    assert (
        classify_risk_tier({"pageLayoutKind": "prose", "confidence": "high"}, ["korean-linebreak-residue"])
        == "medium"
    )
    assert (
        classify_risk_tier({"pageLayoutKind": "list", "confidence": "medium"}, ["boxed-heading"])
        == "medium"
    )
    assert (
        classify_risk_tier({"pageLayoutKind": "decorative/structural", "confidence": "high"}, [])
        == "low"
    )


def test_build_report_summarizes_flagged_pages() -> None:
    report = build_report(
        page_review=[
            {
                "pageNumber": 1,
                "pageLabel": None,
                "chapterSlug": "chapter-a",
                "sectionId": "section-a",
                "pageLayoutKind": "table/form",
                "confidence": "low",
                "hasOverride": True,
                "mergeFirstGroupWithPreviousPage": False,
                "paragraphs": [{"text": "【표】"}],
            },
            {
                "pageNumber": 2,
                "pageLabel": None,
                "chapterSlug": "chapter-a",
                "sectionId": "section-b",
                "pageLayoutKind": "list",
                "confidence": "high",
                "hasOverride": False,
                "mergeFirstGroupWithPreviousPage": True,
                "paragraphs": [{"text": "< 소제목 >"}],
            },
        ],
        search_index=[
            {"entryType": "item", "sectionId": "section-a", "pageStart": 1, "pageEnd": 1},
            {"entryType": "item", "sectionId": "section-b", "pageStart": 1, "pageEnd": 2},
        ],
        document_data={
            "chapters": [
                {
                    "slug": "chapter-a",
                    "html": '<section><img src="./generated/images/table-crops/0002-1.png" /></section>',
                }
            ]
        },
    )

    assert report["summary"]["pageCount"] == 2
    assert report["summary"]["riskCounts"]["high"] == 2
    assert report["flaggedPages"]["multiSectionPages"] == [1]
    assert report["flaggedPages"]["lowConfidencePages"] == [1]
    assert report["flaggedPages"]["overridePages"] == [1]
    assert report["flaggedPages"]["mergePages"] == [2]
    assert report["flaggedPages"]["boxedHeadingPages"] == [1]
    assert report["flaggedPages"]["angleHeadingPages"] == [2]
    assert report["flaggedPages"]["koreanLinebreakResiduePages"] == []
