from __future__ import annotations

from collections import Counter
from typing import Any

from .common import load_generated_json, print_json_summary, write_json


FLAG_PRIORITY = {
    "missing-table-crop": 100,
    "synthetic-table-remains": 95,
    "multi-section-page": 68,
    "low-confidence": 80,
    "has-override": 75,
    "page-merge": 70,
    "structural-fragment-paragraph": 65,
    "boxed-heading": 50,
    "angle-heading": 45,
}

ACCURACY_FLAGS = {
    "missing-table-crop",
    "synthetic-table-remains",
    "multi-section-page",
    "low-confidence",
    "has-override",
    "page-merge",
    "structural-fragment-paragraph",
}


def build_chapter_route(page: dict[str, Any]) -> str | None:
    chapter_slug = page.get("chapterSlug")
    if not chapter_slug:
        return None
    section_id = page.get("sectionId")
    if section_id:
        return f"/chapter/{chapter_slug}/{section_id}"
    return f"/chapter/{chapter_slug}"


def classify_queue_lane(flags: list[str]) -> str:
    if any(flag in ACCURACY_FLAGS for flag in flags):
        return "accuracy-critical"
    return "readability-critical"


def calculate_priority_score(page: dict[str, Any]) -> int:
    flags = [str(flag) for flag in page.get("flags", [])]
    score = sum(FLAG_PRIORITY.get(flag, 10) for flag in flags)

    if str(page.get("pageLayoutKind")) == "table/form":
        score += 12
    if str(page.get("confidence")) == "low":
        score += 8

    overlap_count = int(page.get("sectionOverlapCount") or 0)
    if overlap_count >= 2 and set(flags) != {"multi-section-page"}:
        score += overlap_count * 4

    return score


def summarize_flags(flags: list[str]) -> str:
    ordered = sorted(flags, key=lambda flag: (-FLAG_PRIORITY.get(flag, 0), flag))
    return ", ".join(ordered)


def build_queue_entry(page: dict[str, Any]) -> dict[str, Any]:
    flags = [str(flag) for flag in page.get("flags", [])]
    score = calculate_priority_score(page)

    return {
        "pageNumber": int(page["pageNumber"]),
        "pageLabel": page.get("pageLabel"),
        "chapterSlug": page.get("chapterSlug"),
        "sectionId": page.get("sectionId"),
        "pageLayoutKind": page.get("pageLayoutKind"),
        "confidence": page.get("confidence"),
        "hasOverride": bool(page.get("hasOverride")),
        "mergeFirstGroupWithPreviousPage": bool(page.get("mergeFirstGroupWithPreviousPage")),
        "sectionOverlapCount": int(page.get("sectionOverlapCount") or 0),
        "riskTier": page.get("riskTier"),
        "flags": flags,
        "flagSummary": summarize_flags(flags),
        "priorityScore": score,
        "queueLane": classify_queue_lane(flags),
        "qaPath": f"/qa/page/{int(page['pageNumber'])}",
        "chapterPath": build_chapter_route(page),
    }


def build_markdown(queue_entries: list[dict[str, Any]], summary: dict[str, Any]) -> str:
    lines = [
        "# High-Risk Review Queue",
        "",
        f"- total high-risk pages: {summary['highRiskPageCount']}",
        f"- accuracy-critical: {summary['queueLaneCounts'].get('accuracy-critical', 0)}",
        f"- readability-critical: {summary['queueLaneCounts'].get('readability-critical', 0)}",
        f"- table/form pages in queue: {summary['layoutCounts'].get('table/form', 0)}",
        f"- multi-section pages in queue: {summary['flagCounts'].get('multi-section-page', 0)}",
        f"- low-confidence pages in queue: {summary['flagCounts'].get('low-confidence', 0)}",
        "",
        "## Top 50",
        "",
        "| Rank | Page | Label | Layout | Score | Flags | Chapter | QA Path |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]

    for entry in queue_entries[:50]:
        lines.append(
            "| {rank} | {page} | {label} | {layout} | {score} | {flags} | {chapter} | {qa} |".format(
                rank=entry["priorityRank"],
                page=entry["pageNumber"],
                label=entry.get("pageLabel") or "-",
                layout=entry.get("pageLayoutKind") or "-",
                score=entry["priorityScore"],
                flags=entry["flagSummary"] or "-",
                chapter=entry.get("chapterSlug") or "-",
                qa=entry["qaPath"],
            )
        )

    return "\n".join(lines) + "\n"


def build_queue(page_audit_report: dict[str, Any]) -> dict[str, Any]:
    high_risk_pages = [
        build_queue_entry(page)
        for page in page_audit_report.get("pages", [])
        if page.get("riskTier") == "high"
    ]
    high_risk_pages.sort(
        key=lambda entry: (
            -int(entry["priorityScore"]),
            0 if entry["queueLane"] == "accuracy-critical" else 1,
            int(entry["pageNumber"]),
        )
    )

    for rank, entry in enumerate(high_risk_pages, start=1):
        entry["priorityRank"] = rank

    flag_counts = Counter(flag for entry in high_risk_pages for flag in entry["flags"])
    layout_counts = Counter(str(entry.get("pageLayoutKind") or "") for entry in high_risk_pages)
    lane_counts = Counter(entry["queueLane"] for entry in high_risk_pages)

    summary = {
        "highRiskPageCount": len(high_risk_pages),
        "flagCounts": dict(flag_counts),
        "layoutCounts": dict(layout_counts),
        "queueLaneCounts": dict(lane_counts),
    }

    markdown = build_markdown(high_risk_pages, summary)
    return {
        "summary": summary,
        "queue": high_risk_pages,
        "markdown": markdown,
    }


def main() -> None:
    page_audit_report = load_generated_json("page-audit-report.json")
    queue_report = build_queue(page_audit_report)

    json_target = write_json("page-review-queue.json", {"summary": queue_report["summary"], "queue": queue_report["queue"]})
    markdown_target = json_target.with_suffix(".md")
    markdown_target.write_text(queue_report["markdown"], encoding="utf-8")

    print_json_summary(
        "page-review-queue",
        {
            "jsonTarget": str(json_target),
            "markdownTarget": str(markdown_target),
            "highRiskPageCount": queue_report["summary"]["highRiskPageCount"],
            "accuracyCriticalCount": queue_report["summary"]["queueLaneCounts"].get("accuracy-critical", 0),
            "readabilityCriticalCount": queue_report["summary"]["queueLaneCounts"].get("readability-critical", 0),
        },
    )


if __name__ == "__main__":
    main()
