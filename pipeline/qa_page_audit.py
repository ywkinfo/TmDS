from __future__ import annotations

import re
from collections import Counter, defaultdict
from typing import Any

from .common import load_generated_json, print_json_summary, write_json


BOXED_HEADING_RE = re.compile(r"^[\[【].+[】\]]$")
ANGLE_HEADING_RE = re.compile(r"^<\s*.+\s*>$")
FRAGMENT_PARAGRAPH_RE = re.compile(r"^(?:제|편|\d+)$")


def build_page_entry_overlap(search_index: list[dict[str, Any]]) -> dict[int, set[str]]:
    page_to_entries: dict[int, set[str]] = defaultdict(set)

    for entry in search_index:
        if entry.get("entryType") in {"search-alias", "overview"}:
            continue
        key = f"{entry.get('entryType')}::{entry.get('sectionId')}"
        for page_number in range(int(entry["pageStart"]), int(entry["pageEnd"]) + 1):
            page_to_entries[page_number].add(key)

    return page_to_entries


def chapter_html_by_slug(document_data: dict[str, Any]) -> dict[str, str]:
    return {
        str(chapter["slug"]): str(chapter.get("html", ""))
        for chapter in document_data.get("chapters", [])
    }


def detect_page_flags(
    page: dict[str, Any],
    *,
    section_overlap_count: int,
    chapter_html: str,
) -> list[str]:
    flags: list[str] = []
    texts = [str(paragraph.get("text", "")).strip() for paragraph in page.get("paragraphs", [])]
    non_table_texts = [text for text in texts if text and "|" not in text]
    page_number = int(page["pageNumber"])
    crop_prefix = f"table-crops/{page_number:04d}-"

    if section_overlap_count >= 2:
        flags.append("multi-section-page")
    if str(page.get("confidence")) == "low":
        flags.append("low-confidence")
    if bool(page.get("hasOverride")):
        flags.append("has-override")
    if bool(page.get("mergeFirstGroupWithPreviousPage")):
        flags.append("page-merge")
    if any(BOXED_HEADING_RE.match(text) for text in texts if text):
        flags.append("boxed-heading")
    if any(ANGLE_HEADING_RE.match(text) for text in non_table_texts):
        flags.append("angle-heading")
    if str(page.get("pageLayoutKind")) == "table/form" and crop_prefix not in chapter_html:
        flags.append("missing-table-crop")
    if "table-crops/" in chapter_html and "reader-synthetic-table" in chapter_html:
        flags.append("synthetic-table-remains")
    if any(FRAGMENT_PARAGRAPH_RE.match(text) for text in texts if text):
        flags.append("structural-fragment-paragraph")

    return flags


def classify_risk_tier(page: dict[str, Any], flags: list[str]) -> str:
    page_layout_kind = str(page.get("pageLayoutKind") or "")

    if (
        page_layout_kind == "table/form"
        or "multi-section-page" in flags
        or "low-confidence" in flags
        or "has-override" in flags
        or "page-merge" in flags
    ):
        return "high"

    if page_layout_kind == "list" and (
        "boxed-heading" in flags or "angle-heading" in flags
    ):
        return "medium"

    if page_layout_kind == "decorative/structural":
        return "low"

    if page_layout_kind == "list":
        return "low"

    return "low" if str(page.get("confidence")) == "high" else "medium"


def build_report(
    *,
    page_review: list[dict[str, Any]],
    search_index: list[dict[str, Any]],
    document_data: dict[str, Any],
) -> dict[str, Any]:
    page_to_entries = build_page_entry_overlap(search_index)
    html_by_slug = chapter_html_by_slug(document_data)
    pages: list[dict[str, Any]] = []

    for page in page_review:
        page_number = int(page["pageNumber"])
        chapter_slug = str(page.get("chapterSlug") or "")
        overlap_count = len(page_to_entries.get(page_number, set()))
        flags = detect_page_flags(
            page,
            section_overlap_count=overlap_count,
            chapter_html=html_by_slug.get(chapter_slug, ""),
        )

        pages.append(
            {
                "pageNumber": page_number,
                "pageLabel": page.get("pageLabel"),
                "chapterSlug": page.get("chapterSlug"),
                "sectionId": page.get("sectionId"),
                "pageLayoutKind": page.get("pageLayoutKind"),
                "confidence": page.get("confidence"),
                "hasOverride": bool(page.get("hasOverride")),
                "mergeFirstGroupWithPreviousPage": bool(page.get("mergeFirstGroupWithPreviousPage")),
                "sectionOverlapCount": overlap_count,
                "riskTier": classify_risk_tier(page, flags),
                "flags": flags,
            }
        )

    layout_counts = Counter(str(page.get("pageLayoutKind") or "") for page in page_review)
    confidence_counts = Counter(str(page.get("confidence") or "") for page in page_review)
    risk_counts = Counter(page["riskTier"] for page in pages)
    flag_counts = Counter(flag for page in pages for flag in page["flags"])

    flagged_pages = {
        "multiSectionPages": [page["pageNumber"] for page in pages if "multi-section-page" in page["flags"]],
        "lowConfidencePages": [page["pageNumber"] for page in pages if "low-confidence" in page["flags"]],
        "overridePages": [page["pageNumber"] for page in pages if "has-override" in page["flags"]],
        "mergePages": [page["pageNumber"] for page in pages if "page-merge" in page["flags"]],
        "boxedHeadingPages": [page["pageNumber"] for page in pages if "boxed-heading" in page["flags"]],
        "angleHeadingPages": [page["pageNumber"] for page in pages if "angle-heading" in page["flags"]],
        "tableFormPagesMissingCrop": [page["pageNumber"] for page in pages if "missing-table-crop" in page["flags"]],
        "pagesWithSyntheticTablesRemaining": [page["pageNumber"] for page in pages if "synthetic-table-remains" in page["flags"]],
        "structuralFragmentPages": [page["pageNumber"] for page in pages if "structural-fragment-paragraph" in page["flags"]],
    }

    multi_section_distribution = Counter(
        page["sectionOverlapCount"]
        for page in pages
        if page["sectionOverlapCount"] >= 2
    )

    return {
        "summary": {
            "pageCount": len(page_review),
            "layoutCounts": dict(layout_counts),
            "confidenceCounts": dict(confidence_counts),
            "riskCounts": dict(risk_counts),
            "flagCounts": dict(flag_counts),
            "multiSectionDistribution": dict(multi_section_distribution),
            "overridePageCount": sum(1 for page in pages if page["hasOverride"]),
            "mergePageCount": sum(1 for page in pages if page["mergeFirstGroupWithPreviousPage"]),
        },
        "flaggedPages": flagged_pages,
        "pages": pages,
    }


def main() -> None:
    page_review = load_generated_json("page-review.json")
    search_index = load_generated_json("search-index.json")
    document_data = load_generated_json("document-data.json")

    report = build_report(
        page_review=page_review,
        search_index=search_index,
        document_data=document_data,
    )
    target = write_json("page-audit-report.json", report)
    print_json_summary(
        "page-audit",
        {
            "target": str(target),
            "pageCount": report["summary"]["pageCount"],
            "highRiskPageCount": report["summary"]["riskCounts"].get("high", 0),
            "multiSectionPageCount": len(report["flaggedPages"]["multiSectionPages"]),
            "lowConfidencePageCount": len(report["flaggedPages"]["lowConfidencePages"]),
            "missingTableCropPageCount": len(report["flaggedPages"]["tableFormPagesMissingCrop"]),
        },
    )


if __name__ == "__main__":
    main()
