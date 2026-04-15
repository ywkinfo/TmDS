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

    assert overlap[10] == {"item::a", "item::b", "overview::overview"}
    assert overlap[11] == {"item::b"}


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


def test_classify_risk_tier_promotes_high_risk_signals() -> None:
    assert (
        classify_risk_tier({"pageLayoutKind": "table/form", "confidence": "medium"}, ["missing-table-crop"])
        == "high"
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
