from __future__ import annotations

from pipeline.qa_review_batches import build_batches, split_batches


def test_split_batches_splits_top_entries_into_fixed_size_groups() -> None:
    entries = [{"pageNumber": index} for index in range(1, 23)]

    batches = split_batches(entries, batch_size=10)

    assert [len(batch) for batch in batches] == [10, 10, 2]


def test_build_batches_creates_two_first_review_batches_from_top_twenty() -> None:
    queue = []
    for index in range(1, 26):
        queue.append(
            {
                "priorityRank": index,
                "pageNumber": index,
                "pageLabel": str(index),
                "pageLayoutKind": "table/form" if index <= 5 else "prose",
                "priorityScore": 200 - index,
                "queueLane": "accuracy-critical" if index <= 15 else "readability-critical",
                "flags": ["multi-section-page"] if index <= 10 else ["boxed-heading"],
                "flagSummary": "multi-section-page" if index <= 10 else "boxed-heading",
                "chapterSlug": f"chapter-{index}",
                "qaPath": f"/qa/page/{index}",
                "chapterPath": f"/chapter/chapter-{index}",
            }
        )

    batch_report = build_batches({"queue": queue})

    assert batch_report["summary"]["topPageCount"] == 20
    assert batch_report["summary"]["batchCount"] == 2
    assert batch_report["batches"][0]["batchId"] == "A"
    assert batch_report["batches"][1]["batchId"] == "B"
    assert batch_report["batches"][0]["rankRange"] == {"start": 1, "end": 10}
    assert batch_report["batches"][1]["rankRange"] == {"start": 11, "end": 20}
    assert batch_report["batches"][0]["summary"]["laneCounts"]["accuracy-critical"] == 10
    assert batch_report["batches"][1]["summary"]["laneCounts"]["accuracy-critical"] == 5
    assert batch_report["batches"][1]["summary"]["laneCounts"]["readability-critical"] == 5
