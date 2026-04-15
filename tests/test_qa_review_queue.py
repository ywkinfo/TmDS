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
                    "pageNumber": 12,
                    "pageLabel": None,
                    "chapterSlug": "chapter-c",
                    "sectionId": "section-c",
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
    assert len(queue) == 2
    assert queue[0]["pageNumber"] == 44
    assert queue[0]["priorityRank"] == 1
    assert queue[0]["queueLane"] == "accuracy-critical"
    assert queue[0]["qaPath"] == "/qa/page/44"
    assert queue[0]["chapterPath"] == "/chapter/chapter-a/section-a"
    assert queue[1]["queueLane"] == "readability-critical"
    assert queue_report["summary"]["highRiskPageCount"] == 2
    assert "Top 50" in queue_report["markdown"]
