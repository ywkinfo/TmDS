from __future__ import annotations

from pipeline.qa_review_queue import build_queue, calculate_priority_score


def test_calculate_priority_score_promotes_accuracy_risks_over_readability() -> None:
    low_confidence_table_page = {
        "pageNumber": 44,
        "pageLayoutKind": "table/form",
        "confidence": "low",
        "sectionOverlapCount": 3,
        "flags": ["multi-section-page", "low-confidence"],
    }
    readability_only_page = {
        "pageNumber": 86,
        "pageLayoutKind": "list",
        "confidence": "medium",
        "sectionOverlapCount": 1,
        "flags": ["boxed-heading"],
    }

    assert calculate_priority_score(low_confidence_table_page) > calculate_priority_score(readability_only_page)


def test_calculate_priority_score_ranks_page_merge_above_plain_multi_section() -> None:
    multi_section_only_page = {
        "pageNumber": 45,
        "pageLayoutKind": "prose",
        "confidence": "high",
        "sectionOverlapCount": 4,
        "flags": ["multi-section-page"],
    }
    page_merge_only_page = {
        "pageNumber": 92,
        "pageLayoutKind": "prose",
        "confidence": "high",
        "sectionOverlapCount": 0,
        "flags": ["page-merge"],
    }
    combined_page = {
        "pageNumber": 46,
        "pageLayoutKind": "prose",
        "confidence": "high",
        "sectionOverlapCount": 2,
        "flags": ["multi-section-page", "page-merge"],
    }

    assert calculate_priority_score(page_merge_only_page) > calculate_priority_score(multi_section_only_page)
    assert calculate_priority_score(combined_page) > calculate_priority_score(page_merge_only_page)


def test_calculate_priority_score_ranks_korean_linebreak_residue_above_boxed_heading() -> None:
    residue_page = {
        "pageNumber": 303,
        "pageLayoutKind": "prose",
        "confidence": "high",
        "sectionOverlapCount": 0,
        "flags": ["korean-linebreak-residue"],
    }
    readability_only_page = {
        "pageNumber": 86,
        "pageLayoutKind": "list",
        "confidence": "medium",
        "sectionOverlapCount": 1,
        "flags": ["boxed-heading"],
    }
    page_merge_only_page = {
        "pageNumber": 92,
        "pageLayoutKind": "prose",
        "confidence": "high",
        "sectionOverlapCount": 0,
        "flags": ["page-merge"],
    }

    assert calculate_priority_score(residue_page) > calculate_priority_score(readability_only_page)
    assert calculate_priority_score(page_merge_only_page) > calculate_priority_score(residue_page)


def test_build_queue_ranks_high_risk_pages_and_assigns_paths() -> None:
    queue_report = build_queue(
        {
            "pages": [
                {
                    "pageNumber": 44,
                    "pageLabel": "16",
                    "chapterSlug": "chapter-a",
                    "sectionId": "section-a",
                    "pageLayoutKind": "table/form",
                    "confidence": "low",
                    "hasOverride": False,
                    "mergeFirstGroupWithPreviousPage": False,
                    "sectionOverlapCount": 3,
                    "riskTier": "high",
                    "flags": ["multi-section-page", "low-confidence"],
                },
                {
                    "pageNumber": 86,
                    "pageLabel": "58",
                    "chapterSlug": "chapter-b",
                    "sectionId": "section-b",
                    "pageLayoutKind": "list",
                    "confidence": "medium",
                    "hasOverride": False,
                    "mergeFirstGroupWithPreviousPage": False,
                    "sectionOverlapCount": 1,
                    "riskTier": "high",
                    "flags": ["boxed-heading"],
                },
                {
                    "pageNumber": 303,
                    "pageLabel": "275",
                    "chapterSlug": "chapter-c",
                    "sectionId": "overview",
                    "pageLayoutKind": "prose",
                    "confidence": "low",
                    "hasOverride": False,
                    "mergeFirstGroupWithPreviousPage": False,
                    "sectionOverlapCount": 0,
                    "riskTier": "high",
                    "flags": ["korean-linebreak-residue", "low-confidence"],
                },
                {
                    "pageNumber": 12,
                    "pageLabel": None,
                    "chapterSlug": "chapter-d",
                    "sectionId": "section-d",
                    "pageLayoutKind": "prose",
                    "confidence": "high",
                    "hasOverride": False,
                    "mergeFirstGroupWithPreviousPage": False,
                    "sectionOverlapCount": 1,
                    "riskTier": "low",
                    "flags": [],
                },
            ]
        }
    )

    queue = queue_report["queue"]
    assert len(queue) == 3
    assert queue[0]["pageNumber"] == 44
    assert queue[0]["priorityRank"] == 1
    assert queue[0]["queueLane"] == "accuracy-critical"
    assert queue[0]["qaPath"] == "/qa/page/44"
    assert queue[0]["chapterPath"] == "/chapter/chapter-a/section-a"
    assert queue[1]["pageNumber"] == 303
    assert queue[1]["queueLane"] == "accuracy-critical"
    assert queue[-1]["queueLane"] == "readability-critical"
    assert queue_report["summary"]["highRiskPageCount"] == 3
    assert "Top 50" in queue_report["markdown"]
