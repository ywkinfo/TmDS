from __future__ import annotations

from collections import Counter
from typing import Any

from .common import load_generated_json, print_json_summary, write_json


BATCH_SIZE = 10
TOP_PAGE_COUNT = 20


def split_batches(queue_entries: list[dict[str, Any]], *, batch_size: int = BATCH_SIZE) -> list[list[dict[str, Any]]]:
    return [queue_entries[index : index + batch_size] for index in range(0, len(queue_entries), batch_size)]


def build_batch_summary(entries: list[dict[str, Any]]) -> dict[str, Any]:
    lane_counts = Counter(str(entry.get("queueLane") or "") for entry in entries)
    layout_counts = Counter(str(entry.get("pageLayoutKind") or "") for entry in entries)
    flag_counts = Counter(flag for entry in entries for flag in entry.get("flags", []))

    return {
        "pageCount": len(entries),
        "laneCounts": dict(lane_counts),
        "layoutCounts": dict(layout_counts),
        "flagCounts": dict(flag_counts),
        "pageNumbers": [int(entry["pageNumber"]) for entry in entries],
    }


def build_batches(queue_report: dict[str, Any], *, top_page_count: int = TOP_PAGE_COUNT, batch_size: int = BATCH_SIZE) -> dict[str, Any]:
    queue_entries = list(queue_report.get("queue", []))[:top_page_count]
    batches: list[dict[str, Any]] = []

    for index, entries in enumerate(split_batches(queue_entries, batch_size=batch_size)):
        batch_id = chr(ord("A") + index)
        batches.append(
            {
                "batchId": batch_id,
                "title": f"Batch {batch_id}",
                "pageCount": len(entries),
                "rankRange": {
                    "start": int(entries[0]["priorityRank"]) if entries else None,
                    "end": int(entries[-1]["priorityRank"]) if entries else None,
                },
                "summary": build_batch_summary(entries),
                "entries": entries,
            }
        )

    summary = {
        "topPageCount": len(queue_entries),
        "batchCount": len(batches),
        "batchSize": batch_size,
    }

    return {
        "summary": summary,
        "batches": batches,
    }


def build_markdown(batch_report: dict[str, Any]) -> str:
    lines = [
        "# First Review Batches",
        "",
        f"- top pages covered: {batch_report['summary']['topPageCount']}",
        f"- batch count: {batch_report['summary']['batchCount']}",
        f"- batch size: {batch_report['summary']['batchSize']}",
        "",
    ]

    for batch in batch_report.get("batches", []):
        lines.extend(
            [
                f"## {batch['title']}",
                "",
                f"- rank range: {batch['rankRange']['start']} - {batch['rankRange']['end']}",
                f"- page count: {batch['pageCount']}",
                f"- accuracy-critical: {batch['summary']['laneCounts'].get('accuracy-critical', 0)}",
                f"- readability-critical: {batch['summary']['laneCounts'].get('readability-critical', 0)}",
                "",
                "| Rank | Page | Label | Layout | Score | Flags | Chapter | QA Path | Chapter Path |",
                "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
            ]
        )
        for entry in batch.get("entries", []):
            lines.append(
                "| {rank} | {page} | {label} | {layout} | {score} | {flags} | {chapter} | {qa} | {chapter_path} |".format(
                    rank=entry["priorityRank"],
                    page=entry["pageNumber"],
                    label=entry.get("pageLabel") or "-",
                    layout=entry.get("pageLayoutKind") or "-",
                    score=entry.get("priorityScore"),
                    flags=entry.get("flagSummary") or "-",
                    chapter=entry.get("chapterSlug") or "-",
                    qa=entry.get("qaPath") or "-",
                    chapter_path=entry.get("chapterPath") or "-",
                )
            )
        lines.append("")

    return "\n".join(lines)


def main() -> None:
    queue_report = load_generated_json("page-review-queue.json")
    batch_report = build_batches(queue_report)

    json_target = write_json("page-review-batches.json", batch_report)
    markdown_target = json_target.with_suffix(".md")
    markdown_target.write_text(build_markdown(batch_report) + "\n", encoding="utf-8")

    print_json_summary(
        "page-review-batches",
        {
            "jsonTarget": str(json_target),
            "markdownTarget": str(markdown_target),
            "batchCount": batch_report["summary"]["batchCount"],
            "topPageCount": batch_report["summary"]["topPageCount"],
        },
    )


if __name__ == "__main__":
    main()
