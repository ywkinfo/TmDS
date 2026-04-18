from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
import re
from typing import Any

from .common import (
    DATA_DIR,
    load_generated_json,
    make_excerpt,
    merge_extracted_text_segments,
    normalize_line,
    normalize_search_text,
    print_json_summary,
    repair_extracted_text_spacing,
)
from .qa_review_queue import calculate_priority_score


RESEARCH_DIR = DATA_DIR / "research" / "pdf-web-audit"
BASELINE_FILENAMES = ("page-coverage-ledger.json", "special-sections.json")
FIXED_SEARCH_QUERIES = (
    "머리말",
    "일러두기",
    "부 록",
    "부칙",
    "별첨",
    "개정 연혁",
    "지리적 표시",
    "FTA",
    "재검토기한",
)
TOKEN_RE = re.compile(r"[0-9A-Za-z가-힣§().·ㆍ~∼-]+")


def default_bundle_id() -> str:
    return f"{datetime.now(UTC).date().isoformat()}-r2"


def build_route(chapter_slug: str | None, section_id: str | None = None) -> str | None:
    if not chapter_slug:
        return None
    if section_id and section_id != "overview":
        return f"#/chapter/{chapter_slug}/{section_id}"
    return f"#/chapter/{chapter_slug}"


def normalize_chapter_slug(record: dict[str, Any]) -> str | None:
    chapter_slug = record.get("chapterSlug")
    if chapter_slug:
        return str(chapter_slug)
    slug = record.get("slug")
    if slug:
        return str(slug)
    return None


def reduce_search_entry(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "chapterSlug": normalize_chapter_slug(entry),
        "sectionId": entry.get("sectionId"),
        "sectionTitle": entry.get("sectionTitle"),
        "entryType": entry.get("entryType"),
        "pageStart": int(entry["pageStart"]),
        "pageEnd": int(entry["pageEnd"]),
    }


def reduce_chapter_match(chapter: dict[str, Any]) -> dict[str, Any]:
    return {
        "slug": normalize_chapter_slug(chapter),
        "title": chapter.get("title"),
    }


def build_page_index(records: list[dict[str, Any]], *, start_field: str, end_field: str) -> dict[int, list[dict[str, Any]]]:
    page_index: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        start = int(record[start_field])
        end = int(record[end_field])
        for page_number in range(start, end + 1):
            page_index[page_number].append(record)
    return page_index


def classify_delivery_mode(
    *,
    chapter_matches: list[dict[str, Any]],
    search_entries: list[dict[str, Any]],
    page_layout_kind: str | None,
) -> str | None:
    if chapter_matches:
        return "reader-body"
    if search_entries:
        return "search-only"
    if page_layout_kind == "toc":
        return "toc-transform"
    return None


def build_page_coverage_ledger(
    *,
    inventory: dict[str, Any],
    page_review: list[dict[str, Any]],
    page_audit: dict[str, Any],
    search_index: list[dict[str, Any]],
    document_data: dict[str, Any],
) -> dict[str, Any]:
    review_by_page = {int(page["pageNumber"]): page for page in page_review}
    audit_by_page = {int(page["pageNumber"]): page for page in page_audit.get("pages", [])}
    chapter_page_map = build_page_index(document_data.get("chapters", []), start_field="pageStart", end_field="pageEnd")
    search_page_map = build_page_index(search_index, start_field="pageStart", end_field="pageEnd")

    pages: list[dict[str, Any]] = []
    delivery_mode_counts: Counter[str] = Counter()
    text_pages_not_exposed: list[int] = []
    uncovered_body_pages: list[int] = []
    text_pages_toc_transform: list[int] = []
    null_label_text_pages: list[int] = []

    for inventory_page in inventory.get("pages", []):
        page_number = int(inventory_page["pageNumber"])
        review_page = review_by_page.get(page_number, {})
        audit_page = audit_by_page.get(page_number, {})
        chapter_matches = [
            reduce_chapter_match(chapter)
            for chapter in chapter_page_map.get(page_number, [])
        ]
        search_entries = [
            reduce_search_entry(entry)
            for entry in search_page_map.get(page_number, [])
        ]
        delivery_mode = classify_delivery_mode(
            chapter_matches=chapter_matches,
            search_entries=search_entries,
            page_layout_kind=review_page.get("pageLayoutKind"),
        )

        page_record = {
            "pageNumber": page_number,
            "pageLabel": inventory_page.get("pageLabel"),
            "pageKind": inventory_page.get("pageKind"),
            "hasText": bool(inventory_page.get("hasText")),
            "imageCount": int(inventory_page.get("imageCount") or 0),
            "topLines": list(inventory_page.get("topLines", [])),
            "deliveryMode": delivery_mode,
            "chapterMatches": chapter_matches,
            "searchEntryCount": len(search_entries),
            "searchEntries": search_entries,
            "reviewChapterSlug": normalize_chapter_slug(review_page) if review_page else None,
            "reviewSectionId": review_page.get("sectionId") if review_page else None,
            "riskTier": audit_page.get("riskTier"),
            "flags": list(audit_page.get("flags", [])),
        }
        pages.append(page_record)

        if delivery_mode:
            delivery_mode_counts[delivery_mode] += 1
        if page_record["hasText"] and inventory_page.get("pageLabel") is None:
            null_label_text_pages.append(page_number)
        if delivery_mode == "toc-transform" and page_record["hasText"]:
            text_pages_toc_transform.append(page_number)
        if page_record["hasText"] and delivery_mode is None:
            text_pages_not_exposed.append(page_number)
        if inventory_page.get("pageKind") == "body" and delivery_mode is None:
            uncovered_body_pages.append(page_number)

    toc_pages = [page["pageNumber"] for page in pages if page.get("deliveryMode") == "toc-transform"]
    toc_span = [min(toc_pages), max(toc_pages)] if toc_pages else []
    text_page_count = sum(1 for page in inventory.get("pages", []) if page.get("hasText"))

    return {
        "summary": {
            "pageCount": len(pages),
            "deliveryModeCounts": dict(delivery_mode_counts),
            "textPageCount": text_page_count,
            "uncoveredBodyPages": uncovered_body_pages,
            "uncoveredBodyPageCount": len(uncovered_body_pages),
            "textPagesNotExposed": text_pages_not_exposed,
            "textPagesTocTransform": text_pages_toc_transform,
            "nullLabelTextPages": null_label_text_pages,
            "tocSpan": toc_span,
        },
        "pages": pages,
    }


def chapter_has_part_intro(chapter: dict[str, Any]) -> bool:
    return 'id="part-intro"' in str(chapter.get("html", ""))


def normalize_query_text(value: str | None) -> str:
    return normalize_line((value or "").casefold())


def contains_term(*values: Any, term: str) -> bool:
    normalized_term = normalize_query_text(term)
    return any(normalized_term in normalize_query_text(str(value or "")) for value in values)


def _append_special_record(records: list[dict[str, Any]], record: dict[str, Any]) -> None:
    unique_key = tuple(record.get(field) for field in ("via", "chapterSlug", "sectionId", "pageStart", "pageEnd", "matchedTerm"))
    existing_keys = {
        tuple(existing.get(field) for field in ("via", "chapterSlug", "sectionId", "pageStart", "pageEnd", "matchedTerm"))
        for existing in records
    }
    if unique_key not in existing_keys:
        records.append(record)


def build_special_sections(search_index: list[dict[str, Any]], document_data: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    sections: dict[str, list[dict[str, Any]]] = {
        "front_preface": [],
        "front_notes": [],
        "toc": [],
        "part_intro": [],
        "revision_history": [],
        "legend": [],
        "appendix": [],
        "reconsideration_deadline": [],
        "fta_gi": [],
    }

    for entry in search_index:
        chapter_slug = normalize_chapter_slug(entry)
        section_title = str(entry.get("sectionTitle") or "")
        part_title = str(entry.get("partTitle") or "")
        chapter_title = str(entry.get("chapterTitle") or "")
        text = str(entry.get("text") or "")
        excerpt = str(entry.get("excerpt") or "")
        record = {
            "via": "search-index",
            "chapterSlug": chapter_slug,
            "sectionId": entry.get("sectionId"),
            "sectionTitle": entry.get("sectionTitle"),
            "entryType": entry.get("entryType"),
            "pageStart": int(entry["pageStart"]),
            "pageEnd": int(entry["pageEnd"]),
        }

        if chapter_slug == "front-preface":
            _append_special_record(sections["front_preface"], {**record, "matchedTerm": "머리말"})
        if chapter_slug == "front-notes":
            _append_special_record(sections["front_notes"], {**record, "matchedTerm": "일러두기"})
        if entry.get("entryType") == "part-intro":
            _append_special_record(sections["part_intro"], {**record, "matchedTerm": section_title})
        if section_title == "개정 연혁":
            _append_special_record(sections["revision_history"], {**record, "matchedTerm": section_title})
        if part_title == "부 록":
            _append_special_record(sections["appendix"], {**record, "matchedTerm": "부록"})
        if contains_term(section_title, chapter_title, text, excerpt, term="부칙"):
            _append_special_record(sections["appendix"], {**record, "matchedTerm": "부칙"})
        if contains_term(section_title, chapter_title, text, excerpt, term="별첨"):
            _append_special_record(sections["appendix"], {**record, "matchedTerm": "별첨"})
        if contains_term(section_title, chapter_title, text, excerpt, term="재검토기한"):
            _append_special_record(sections["reconsideration_deadline"], {**record, "matchedTerm": "재검토기한"})
        if contains_term(section_title, chapter_title, text, excerpt, term="지리적 표시"):
            _append_special_record(sections["fta_gi"], {**record, "matchedTerm": "지리적 표시"})
        if contains_term(section_title, chapter_title, text, excerpt, term="FTA"):
            _append_special_record(sections["fta_gi"], {**record, "matchedTerm": "FTA"})

    for chapter in document_data.get("chapters", []):
        chapter_slug = normalize_chapter_slug(chapter)
        title = str(chapter.get("title") or "")
        part_title = str(chapter.get("partTitle") or "")
        summary = str(chapter.get("summary") or "")
        record = {
            "via": "document-data",
            "chapterSlug": chapter_slug,
            "title": chapter.get("title"),
            "pageStart": int(chapter["pageStart"]),
            "pageEnd": int(chapter["pageEnd"]),
        }

        if chapter_slug == "front-preface":
            _append_special_record(sections["front_preface"], {**record, "matchedTerm": "머리말"})
        if chapter_slug == "front-notes":
            _append_special_record(sections["front_notes"], {**record, "matchedTerm": "일러두기"})
        if chapter_has_part_intro(chapter):
            _append_special_record(sections["part_intro"], {**record, "matchedTerm": part_title})
        if "개정내용" in title or "개정 연혁" in title:
            _append_special_record(sections["revision_history"], {**record, "matchedTerm": title})
        if part_title == "부 록":
            _append_special_record(sections["appendix"], {**record, "matchedTerm": "부록"})
        if contains_term(title, summary, term="부칙"):
            _append_special_record(sections["appendix"], {**record, "matchedTerm": "부칙"})
        if contains_term(title, summary, term="별첨"):
            _append_special_record(sections["appendix"], {**record, "matchedTerm": "별첨"})
        if contains_term(title, summary, term="재검토기한"):
            _append_special_record(sections["reconsideration_deadline"], {**record, "matchedTerm": "재검토기한"})
        if contains_term(title, summary, term="지리적 표시"):
            _append_special_record(sections["fta_gi"], {**record, "matchedTerm": "지리적 표시"})
        if contains_term(title, summary, term="FTA"):
            _append_special_record(sections["fta_gi"], {**record, "matchedTerm": "FTA"})

    for key, records in sections.items():
        records.sort(key=lambda record: (int(record.get("pageStart") or 0), str(record.get("chapterSlug") or ""), str(record.get("via") or "")))
        sections[key] = records
    return sections


def build_search_corpus(search_index: list[dict[str, Any]]) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    entry_type_counts: Counter[str] = Counter()
    routes: set[str] = set()
    chapters: set[str] = set()

    for entry in search_index:
        chapter_slug = normalize_chapter_slug(entry)
        section_id = entry.get("sectionId")
        route = build_route(chapter_slug, str(section_id) if section_id else None)
        corpus_entry = {
            "id": entry.get("id"),
            "chapterSlug": chapter_slug,
            "chapterTitle": entry.get("chapterTitle"),
            "sectionId": section_id,
            "sectionTitle": entry.get("sectionTitle"),
            "entryType": entry.get("entryType"),
            "partTitle": entry.get("partTitle"),
            "pageStart": int(entry["pageStart"]),
            "pageEnd": int(entry["pageEnd"]),
            "pageLabelStart": entry.get("pageLabelStart"),
            "pageLabelEnd": entry.get("pageLabelEnd"),
            "route": route,
            "text": str(entry.get("text") or ""),
            "excerpt": str(entry.get("excerpt") or ""),
        }
        entries.append(corpus_entry)
        entry_type_counts[str(entry.get("entryType") or "")] += 1
        if route:
            routes.add(route)
        if chapter_slug:
            chapters.add(chapter_slug)

    return {
        "summary": {
            "entryCount": len(entries),
            "entryTypeCounts": dict(entry_type_counts),
            "chapterCount": len(chapters),
            "routeCount": len(routes),
        },
        "entries": entries,
    }


def build_search_queries(special_sections: dict[str, list[dict[str, Any]]]) -> list[str]:
    queries: list[str] = []
    seen: set[str] = set()
    for query in FIXED_SEARCH_QUERIES:
        normalized = normalize_line(query)
        if normalized in seen:
            continue
        seen.add(normalized)
        queries.append(query)
    for section_name in ("front_preface", "front_notes", "part_intro", "revision_history", "appendix"):
        for record in special_sections.get(section_name, []):
            term = normalize_line(str(record.get("matchedTerm") or ""))
            if not term or term in seen:
                continue
            seen.add(term)
            queries.append(term)
    return queries


def search_corpus_entries(query: str, corpus_entries: list[dict[str, Any]], *, limit: int = 5) -> list[dict[str, Any]]:
    normalized_query = normalize_query_text(query)
    if not normalized_query:
        return []

    ranked: list[tuple[tuple[int, int, str, str], dict[str, Any]]] = []
    for entry in corpus_entries:
        title_text = normalize_query_text(entry.get("chapterTitle"))
        section_text = normalize_query_text(entry.get("sectionTitle"))
        part_text = normalize_query_text(entry.get("partTitle"))
        body_text = normalize_query_text(
            " ".join(
                str(entry.get(field) or "")
                for field in ("chapterTitle", "sectionTitle", "partTitle", "text")
            )
        )
        if normalized_query not in body_text:
            continue

        score = 100
        if normalized_query == section_text or normalized_query == title_text:
            score = 400
        elif normalized_query == part_text:
            score = 350
        elif section_text.startswith(normalized_query) or title_text.startswith(normalized_query):
            score = 300
        elif part_text.startswith(normalized_query):
            score = 250
        elif normalized_query in section_text or normalized_query in title_text:
            score = 220

        ranked.append(
            (
                (-score, int(entry["pageStart"]), str(entry.get("chapterSlug") or ""), str(entry.get("sectionId") or "")),
                {
                    "chapterSlug": entry.get("chapterSlug"),
                    "sectionId": entry.get("sectionId"),
                    "title": entry.get("sectionTitle") or entry.get("chapterTitle"),
                    "entryType": entry.get("entryType"),
                    "pageStart": int(entry["pageStart"]),
                    "pageEnd": int(entry["pageEnd"]),
                    "route": entry.get("route"),
                    "score": score,
                },
            )
        )

    ranked.sort(key=lambda item: item[0])
    return [match for _, match in ranked[:limit]]


def build_search_results(search_corpus: dict[str, Any], special_sections: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    queries = build_search_queries(special_sections)
    results: list[dict[str, Any]] = []

    for query in queries:
        matches = search_corpus_entries(query, search_corpus.get("entries", []))
        results.append(
            {
                "query": query,
                "matchCount": len(matches),
                "topMatches": matches,
            }
        )

    matched_query_count = sum(1 for result in results if result["matchCount"] > 0)
    return {
        "summary": {
            "queryCount": len(results),
            "matchedQueryCount": matched_query_count,
            "emptyQueryCount": len(results) - matched_query_count,
        },
        "results": results,
    }


def build_search_checks(search_results: dict[str, Any]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    for result in search_results.get("results", []):
        top_match = result.get("topMatches", [None])[0] if result.get("topMatches") else None
        canonical_route = (
            build_route(top_match.get("chapterSlug"), top_match.get("sectionId"))
            if isinstance(top_match, dict)
            else None
        )
        checks.append(
            {
                "query": result.get("query"),
                "result": "match" if int(result.get("matchCount") or 0) > 0 else "empty",
                "route": canonical_route,
                "evidence": "offline expected runtime route from top match" if top_match else "offline search corpus produced no match",
            }
        )
    return checks


def build_chapter_html_map(document_data: dict[str, Any]) -> dict[str, str]:
    return {
        str(chapter["slug"]): str(chapter.get("html") or "")
        for chapter in document_data.get("chapters", [])
        if chapter.get("slug")
    }


def build_chapter_record_map(document_data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(chapter["slug"]): chapter
        for chapter in document_data.get("chapters", [])
        if chapter.get("slug")
    }


def build_non_alias_search_page_map(search_index: list[dict[str, Any]]) -> dict[int, list[dict[str, Any]]]:
    non_alias_entries = [entry for entry in search_index if entry.get("entryType") != "search-alias"]
    return build_page_index(non_alias_entries, start_field="pageStart", end_field="pageEnd")


def tokenize_comparison_text(value: str) -> list[str]:
    return TOKEN_RE.findall(normalize_search_text(value))


def count_token_diff(source_tokens: list[str], compared_tokens: list[str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    source_counts = Counter(source_tokens)
    compared_counts = Counter(compared_tokens)
    missing_tokens = [
        {"token": token, "count": source_counts[token] - compared_counts.get(token, 0)}
        for token in sorted(source_counts)
        if source_counts[token] > compared_counts.get(token, 0)
    ]
    added_tokens = [
        {"token": token, "count": compared_counts[token] - source_counts.get(token, 0)}
        for token in sorted(compared_counts)
        if compared_counts[token] > source_counts.get(token, 0)
    ]
    return missing_tokens, added_tokens


def section_marker_found(chapter_html: str, section_id: str | None) -> bool:
    return bool(section_id) and f'id="{section_id}"' in chapter_html


def build_pdf_page_text(page_review_entry: dict[str, Any]) -> str:
    paragraph_texts = [
        repair_extracted_text_spacing(str(paragraph.get("text") or ""))
        for paragraph in page_review_entry.get("paragraphs", [])
        if normalize_line(str(paragraph.get("text") or ""))
    ]
    return merge_extracted_text_segments(*paragraph_texts)


def build_render_candidate_entries(page_number: int, search_page_map: dict[int, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for entry in search_page_map.get(page_number, []):
        chapter_slug = normalize_chapter_slug(entry)
        section_id = entry.get("sectionId")
        candidates.append(
            {
                "chapterSlug": chapter_slug,
                "sectionId": section_id,
                "sectionTitle": entry.get("sectionTitle"),
                "entryType": entry.get("entryType"),
                "pageStart": int(entry["pageStart"]),
                "pageEnd": int(entry["pageEnd"]),
                "route": build_route(chapter_slug, str(section_id) if section_id else None),
                "text": str(entry.get("text") or ""),
                "excerpt": make_excerpt(str(entry.get("text") or "")),
            }
        )
    candidates.sort(
        key=lambda entry: (
            int(entry["pageStart"]),
            int(entry["pageEnd"]),
            str(entry.get("chapterSlug") or ""),
            str(entry.get("sectionId") or ""),
        )
    )
    return candidates


def merge_render_candidate_text(candidates: list[dict[str, Any]]) -> str:
    return merge_extracted_text_segments(*(str(candidate.get("text") or "") for candidate in candidates))


def build_representative_locator(page_record: dict[str, Any], candidate_entries: list[dict[str, Any]]) -> dict[str, Any]:
    chapter_slug = page_record.get("reviewChapterSlug")
    section_id = page_record.get("reviewSectionId")
    if chapter_slug:
        return {
            "chapterSlug": chapter_slug,
            "sectionId": section_id,
            "route": build_route(str(chapter_slug), str(section_id) if section_id else None),
            "source": "page-review",
        }
    if candidate_entries:
        candidate = candidate_entries[0]
        return {
            "chapterSlug": candidate.get("chapterSlug"),
            "sectionId": candidate.get("sectionId"),
            "route": candidate.get("route"),
            "source": "search-index-candidate",
        }
    return {
        "chapterSlug": None,
        "sectionId": None,
        "route": None,
        "source": "none",
    }


def build_page_comparison_limitations(
    *,
    candidate_entries: list[dict[str, Any]],
    chapter_found: bool,
    section_found: bool,
    page_flags: list[str],
    merge_first_group_with_previous_page: bool,
) -> list[str]:
    limitations = [
        "PDF-side text comes from repaired page-review paragraphs, not OCR or browser text.",
        "Rendered-side text comes from overlapping non-search-alias search entries, not page-exact browser extraction.",
        "document-data HTML checks are coarse evidence only and do not prove exact page-to-HTML alignment.",
    ]
    if not candidate_entries:
        limitations.append("No overlapping non-search-alias search entries were available for this page.")
    elif len(candidate_entries) >= 2:
        limitations.append("Multiple overlapping non-search-alias sections make attribution ambiguous for this page.")
    if not chapter_found:
        limitations.append("Representative chapter HTML was not found in document-data.")
    elif not section_found:
        limitations.append("Representative section marker was not found in chapter HTML, so section evidence is coarse only.")
    if "multi-section-page" in page_flags:
        limitations.append("This page is flagged as multi-section-page, so page-level attribution remains ambiguous even when a representative section is available.")
    if "page-merge" in page_flags or merge_first_group_with_previous_page:
        limitations.append("This page is flagged for page-merge behavior, so page-level fidelity cannot be treated as page-exact.")
    return limitations


def classify_comparison_status(
    *,
    pdf_tokens: list[str],
    render_tokens: list[str],
    candidate_entries: list[dict[str, Any]],
    chapter_found: bool,
    section_found: bool,
    page_flags: list[str],
    merge_first_group_with_previous_page: bool,
) -> str:
    if not pdf_tokens or not render_tokens or not candidate_entries or not chapter_found:
        return "unsupported"
    if len(candidate_entries) >= 2 or not section_found:
        return "ambiguous"
    if "multi-section-page" in page_flags or "page-merge" in page_flags or merge_first_group_with_previous_page:
        return "ambiguous"
    return "candidate-backed"


def build_fidelity_selection_candidates(
    *,
    page_coverage_ledger: dict[str, Any],
    page_review: list[dict[str, Any]],
    page_audit: dict[str, Any],
) -> tuple[list[int], list[int], dict[str, list[int]]]:
    coverage_by_page = {int(page["pageNumber"]): page for page in page_coverage_ledger.get("pages", [])}
    review_by_page = {int(page["pageNumber"]): page for page in page_review}
    audit_by_page = {int(page["pageNumber"]): page for page in page_audit.get("pages", [])}

    residue_pages = sorted(
        page_number
        for page_number, audit_page in audit_by_page.items()
        if "korean-linebreak-residue" in audit_page.get("flags", [])
    )

    exclusions: dict[str, list[int]] = defaultdict(list)
    eligible_high_risk_pages: list[dict[str, Any]] = []
    for page_number, audit_page in audit_by_page.items():
        review_page = review_by_page.get(page_number, {})
        coverage_page = coverage_by_page.get(page_number, {})
        if audit_page.get("riskTier") != "high":
            continue
        if review_page.get("pageLayoutKind") != "prose":
            exclusions["non-prose-layout"].append(page_number)
            continue
        if coverage_page.get("deliveryMode") != "reader-body":
            exclusions["not-reader-body"].append(page_number)
            continue
        if coverage_page.get("pageKind") != "body":
            exclusions["not-body-page-kind"].append(page_number)
            continue
        eligible_high_risk_pages.append(
            {
                "pageNumber": page_number,
                "pageLayoutKind": review_page.get("pageLayoutKind"),
                "confidence": review_page.get("confidence"),
                "hasOverride": review_page.get("hasOverride"),
                "mergeFirstGroupWithPreviousPage": review_page.get("mergeFirstGroupWithPreviousPage"),
                "sectionOverlapCount": audit_page.get("sectionOverlapCount"),
                "flags": audit_page.get("flags", []),
            }
        )

    eligible_high_risk_pages.sort(key=lambda page: (-calculate_priority_score(page), int(page["pageNumber"])))
    selected_high_risk_pages = [int(page["pageNumber"]) for page in eligible_high_risk_pages[:30]]
    if len(eligible_high_risk_pages) > 30:
        exclusions["sample-cap"].extend(int(page["pageNumber"]) for page in eligible_high_risk_pages[30:])

    return residue_pages, selected_high_risk_pages, {reason: sorted(values) for reason, values in exclusions.items()}


def build_content_fidelity_diff(
    *,
    page_coverage_ledger: dict[str, Any],
    page_review: list[dict[str, Any]],
    page_audit: dict[str, Any],
    search_index: list[dict[str, Any]],
    document_data: dict[str, Any],
) -> dict[str, Any]:
    coverage_by_page = {int(page["pageNumber"]): page for page in page_coverage_ledger.get("pages", [])}
    review_by_page = {int(page["pageNumber"]): page for page in page_review}
    audit_by_page = {int(page["pageNumber"]): page for page in page_audit.get("pages", [])}
    search_page_map = build_non_alias_search_page_map(search_index)
    chapter_html_map = build_chapter_html_map(document_data)
    chapter_record_map = build_chapter_record_map(document_data)
    residue_pages, selected_high_risk_pages, excluded_high_risk_pages = build_fidelity_selection_candidates(
        page_coverage_ledger=page_coverage_ledger,
        page_review=page_review,
        page_audit=page_audit,
    )

    selected_page_numbers = sorted(set(residue_pages) | set(selected_high_risk_pages))
    pages: list[dict[str, Any]] = []
    status_counts: Counter[str] = Counter()
    sampled_high_risk_missing_token_count = 0
    sampled_high_risk_pdf_token_count = 0

    for page_number in selected_page_numbers:
        coverage_page = coverage_by_page.get(page_number, {})
        review_page = review_by_page.get(page_number, {})
        audit_page = audit_by_page.get(page_number, {})
        candidate_entries = build_render_candidate_entries(page_number, search_page_map)
        representative_locator = build_representative_locator(coverage_page, candidate_entries)
        representative_chapter_slug = representative_locator.get("chapterSlug")
        representative_section_id = representative_locator.get("sectionId")
        chapter_html = chapter_html_map.get(str(representative_chapter_slug or ""), "")
        chapter_record = chapter_record_map.get(str(representative_chapter_slug or ""))
        chapter_found = chapter_record is not None
        section_found = section_marker_found(chapter_html, str(representative_section_id) if representative_section_id else None)

        pdf_text = build_pdf_page_text(review_page)
        render_text = merge_render_candidate_text(candidate_entries)
        pdf_tokens = tokenize_comparison_text(pdf_text)
        render_tokens = tokenize_comparison_text(render_text)
        missing_tokens, added_tokens = count_token_diff(pdf_tokens, render_tokens)
        status = classify_comparison_status(
            pdf_tokens=pdf_tokens,
            render_tokens=render_tokens,
            candidate_entries=candidate_entries,
            chapter_found=chapter_found,
            section_found=section_found,
            page_flags=list(audit_page.get("flags", [])),
            merge_first_group_with_previous_page=bool(review_page.get("mergeFirstGroupWithPreviousPage")),
        )
        status_counts[status] += 1
        reordered_candidates_heuristic = (
            len(candidate_entries) >= 2
            and bool(representative_section_id)
            and str(candidate_entries[0].get("sectionId") or "") != str(representative_section_id)
        )
        included_by: list[str] = []
        if page_number in residue_pages:
            included_by.append("korean-linebreak-residue")
        if page_number in selected_high_risk_pages:
            included_by.append("high-risk-prose-sample")

        if "high-risk-prose-sample" in included_by and status in {"candidate-backed", "ambiguous"}:
            sampled_high_risk_missing_token_count += sum(item["count"] for item in missing_tokens)
            sampled_high_risk_pdf_token_count += len(pdf_tokens)

        pages.append(
            {
                "pageNumber": page_number,
                "pageLabel": coverage_page.get("pageLabel"),
                "pageKind": coverage_page.get("pageKind"),
                "deliveryMode": coverage_page.get("deliveryMode"),
                "pageLayoutKind": review_page.get("pageLayoutKind"),
                "riskTier": audit_page.get("riskTier"),
                "flags": list(audit_page.get("flags", [])),
                "includedBy": included_by,
                "representativeLocator": representative_locator,
                "candidateEntries": [
                    {
                        key: candidate.get(key)
                        for key in (
                            "chapterSlug",
                            "sectionId",
                            "sectionTitle",
                            "entryType",
                            "pageStart",
                            "pageEnd",
                            "route",
                            "excerpt",
                        )
                    }
                    for candidate in candidate_entries
                ],
                "coarseRenderEvidence": {
                    "chapterFound": chapter_found,
                    "sectionMarkerFound": section_found,
                    "chapterPageSpan": (
                        {
                            "pageStart": int(chapter_record["pageStart"]),
                            "pageEnd": int(chapter_record["pageEnd"]),
                        }
                        if chapter_record is not None
                        else None
                    ),
                },
                "pdfTextExcerpt": make_excerpt(pdf_text),
                "renderTextExcerpt": make_excerpt(render_text),
                "tokenCounts": {
                    "pdfTokenCount": len(pdf_tokens),
                    "renderTokenCount": len(render_tokens),
                    "missingTokenCount": sum(item["count"] for item in missing_tokens),
                    "addedTokenCount": sum(item["count"] for item in added_tokens),
                },
                "diffMetrics": {
                    "missingTokens": missing_tokens,
                    "addedTokens": added_tokens,
                    "reorderedCandidatesHeuristic": reordered_candidates_heuristic,
                },
                "comparisonStatus": status,
                "limitations": build_page_comparison_limitations(
                    candidate_entries=candidate_entries,
                    chapter_found=chapter_found,
                    section_found=section_found,
                    page_flags=list(audit_page.get("flags", [])),
                    merge_first_group_with_previous_page=bool(review_page.get("mergeFirstGroupWithPreviousPage")),
                ),
            }
        )

    sampled_high_risk_token_loss_rate = (
        sampled_high_risk_missing_token_count / sampled_high_risk_pdf_token_count
        if sampled_high_risk_pdf_token_count
        else None
    )
    return {
        "summary": {
            "comparedPageCount": len(pages),
            "candidateBackedPageCount": status_counts.get("candidate-backed", 0),
            "ambiguousPageCount": status_counts.get("ambiguous", 0),
            "unsupportedPageCount": status_counts.get("unsupported", 0),
            "residuePageCount": len(residue_pages),
            "sampledHighRiskPageCount": len(selected_high_risk_pages),
            "sampledHighRiskTokenLossRate": sampled_high_risk_token_loss_rate,
            "sampledHighRiskTokenLossRateBasis": {
                "missingTokenCount": sampled_high_risk_missing_token_count,
                "pdfTokenCount": sampled_high_risk_pdf_token_count,
                "includedStatuses": ["candidate-backed", "ambiguous"],
            },
        },
        "sampling": {
            "residuePages": {
                "selectionRule": "include all pages flagged with korean-linebreak-residue",
                "includedPageNumbers": residue_pages,
                "pageCount": len(residue_pages),
            },
            "highRiskProseSample": {
                "selectionRule": "deterministic top-priority sample of up to 30 high-risk prose pages",
                "includedPageNumbers": selected_high_risk_pages,
                "pageCount": len(selected_high_risk_pages),
                "exclusions": excluded_high_risk_pages,
                "sampleSizeCap": 30,
                "exclusionNotes": [
                    "Pages are excluded only if they are not reader-body or not body pageKind. multi-section-page and page-merge pages remain eligible but will usually stay ambiguous in the fidelity output.",
                    "Ordering uses qa_review_queue.calculate_priority_score for deterministic sampling.",
                ],
            },
        },
        "pages": pages,
    }


def load_baseline_artifacts(baseline_dir: Path | None) -> dict[str, Any]:
    if baseline_dir is None or not baseline_dir.exists():
        return {}

    artifacts: dict[str, Any] = {}
    for filename in BASELINE_FILENAMES:
        path = baseline_dir / filename
        if not path.exists():
            continue
        artifacts[filename] = json.loads(path.read_text(encoding="utf-8"))
    return artifacts


def build_regression_diff(
    *,
    bundle_id: str,
    baseline_bundle_id: str | None,
    baseline_artifacts: dict[str, Any],
    page_coverage_ledger: dict[str, Any],
    special_sections: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    current_artifacts = {
        "page-coverage-ledger.json": page_coverage_ledger,
        "special-sections.json": special_sections,
    }
    artifacts: dict[str, Any] = {}
    unchanged: list[str] = []
    changed: list[str] = []
    baseline_missing: list[str] = []

    for filename, current in current_artifacts.items():
        baseline = baseline_artifacts.get(filename)
        if baseline is None:
            baseline_missing.append(filename)
            artifacts[filename] = {"status": "baseline-missing"}
            continue
        if filename == "page-coverage-ledger.json":
            baseline_summary = baseline.get("summary", {})
            current_summary = current.get("summary", {})
            summary_changed_keys = sorted(
                key
                for key in set(baseline_summary) | set(current_summary)
                if baseline_summary.get(key) != current_summary.get(key)
            )
            status = "unchanged" if not summary_changed_keys else "changed"
            artifacts[filename] = {
                "status": status,
                "summaryChangedKeys": summary_changed_keys,
            }
        else:
            baseline_counts = {key: len(value) for key, value in baseline.items()}
            current_counts = {key: len(value) for key, value in current.items()}
            changed_groups = sorted(
                key
                for key in set(baseline_counts) | set(current_counts)
                if baseline_counts.get(key) != current_counts.get(key)
            )
            status = "unchanged" if not changed_groups else "changed"
            artifacts[filename] = {
                "status": status,
                "baselineGroupCounts": baseline_counts,
                "currentGroupCounts": current_counts,
                "changedGroups": changed_groups,
            }

        if artifacts[filename]["status"] == "unchanged":
            unchanged.append(filename)
        else:
            changed.append(filename)

    return {
        "summary": {
            "bundleId": bundle_id,
            "baselineBundleId": baseline_bundle_id,
            "changedArtifacts": changed,
            "unchangedArtifacts": unchanged,
            "baselineMissingArtifacts": baseline_missing,
            "newArtifacts": [
                "content-fidelity-diff.json",
                "search-corpus.json",
                "search-results.json",
                "search-checks.json",
                "regression-diff.json",
                "ledger.md",
            ],
        },
        "artifacts": artifacts,
    }


def build_ledger_markdown(
    *,
    bundle_id: str,
    page_coverage_ledger: dict[str, Any],
    special_sections: dict[str, list[dict[str, Any]]],
    search_corpus: dict[str, Any],
    search_results: dict[str, Any],
    content_fidelity_diff: dict[str, Any],
    regression_diff: dict[str, Any],
    baseline_bundle_id: str | None,
) -> str:
    coverage_summary = page_coverage_ledger["summary"]
    search_summary = search_results["summary"]
    fidelity_summary = content_fidelity_diff["summary"]
    regression_summary = regression_diff["summary"]
    lines = [
        f"# PDF ↔ Web Audit R2 Bundle ({bundle_id})",
        "",
        "## 1. Bundle mode",
        "",
        "- mode: offline derived bundle",
        "- source of truth: `data/generated/`",
        "- manual/browser evidence: not regenerated here; any manual verification remains manual-only",
    ]
    if baseline_bundle_id:
        lines.append(f"- baseline reference: `data/research/pdf-web-audit/{baseline_bundle_id}/`")
    lines.extend(
        [
            "",
            "## 2. Coverage summary",
            "",
            f"- page count: `{coverage_summary['pageCount']}`",
            f"- delivery modes: `reader-body {coverage_summary['deliveryModeCounts'].get('reader-body', 0)}`, `toc-transform {coverage_summary['deliveryModeCounts'].get('toc-transform', 0)}`, `search-only {coverage_summary['deliveryModeCounts'].get('search-only', 0)}`",
            f"- text pages not exposed: `{coverage_summary['textPagesNotExposed']}`",
            f"- uncovered body pages: `{coverage_summary['uncoveredBodyPages']}`",
            f"- toc span: `{coverage_summary['tocSpan']}`",
            "",
            "## 3. Special sections",
            "",
        ]
    )
    for key in (
        "front_preface",
        "front_notes",
        "toc",
        "part_intro",
        "revision_history",
        "legend",
        "appendix",
        "reconsideration_deadline",
        "fta_gi",
    ):
        lines.append(f"- `{key}`: `{len(special_sections.get(key, []))}` record(s)")
    lines.extend(
        [
            "",
            "## 4. Offline search artifacts",
            "",
            f"- search corpus entries: `{search_corpus['summary']['entryCount']}`",
            f"- query count: `{search_summary['queryCount']}`",
            f"- matched queries: `{search_summary['matchedQueryCount']}`",
            f"- empty queries: `{search_summary['emptyQueryCount']}`",
            "- `search-checks.json` contains the offline top-match summary for the fixed query set.",
            "",
            "## 5. First-pass content fidelity diff",
            "",
            f"- compared pages: `{fidelity_summary['comparedPageCount']}`",
            f"- residue pages included: `{fidelity_summary['residuePageCount']}`",
            f"- sampled high-risk prose pages: `{fidelity_summary['sampledHighRiskPageCount']}`",
            f"- statuses: `candidate-backed {fidelity_summary['candidateBackedPageCount']}`, `ambiguous {fidelity_summary['ambiguousPageCount']}`, `unsupported {fidelity_summary['unsupportedPageCount']}`",
            f"- sampled high-risk token loss rate: `{fidelity_summary['sampledHighRiskTokenLossRate']}`",
            "- `content-fidelity-diff.json` compares repaired page-review paragraph text to overlapping non-alias search-entry text, with only coarse chapter/section HTML evidence.",
            "",
            "## 6. Regression diff",
            "",
            f"- changed artifacts vs baseline: `{regression_summary['changedArtifacts']}`",
            f"- unchanged artifacts vs baseline: `{regression_summary['unchangedArtifacts']}`",
            f"- baseline-missing artifacts: `{regression_summary['baselineMissingArtifacts']}`",
            "",
            "## 7. Generated files",
            "",
            "- `page-coverage-ledger.json`",
            "- `special-sections.json`",
            "- `content-fidelity-diff.json`",
            "- `regression-diff.json`",
            "- `search-corpus.json`",
            "- `search-results.json`",
            "- `search-checks.json`",
            "- `ledger.md`",
            "",
            "## 8. Manual verification status",
            "",
            "- Browser screenshots, navigation checks, and other manual evidence are intentionally not synthesized in this offline R2 bundle.",
            "- If a previous manually verified bundle exists, treat it as manual evidence only rather than as regenerated proof.",
        ]
    )
    return "\n".join(lines) + "\n"


def build_bundle_artifacts(
    *,
    bundle_id: str,
    inventory: dict[str, Any],
    page_review: list[dict[str, Any]],
    page_audit: dict[str, Any],
    search_index: list[dict[str, Any]],
    document_data: dict[str, Any],
    baseline_artifacts: dict[str, Any] | None = None,
    baseline_bundle_id: str | None = None,
) -> dict[str, Any]:
    baseline_payload = baseline_artifacts or {}
    page_coverage_ledger = build_page_coverage_ledger(
        inventory=inventory,
        page_review=page_review,
        page_audit=page_audit,
        search_index=search_index,
        document_data=document_data,
    )
    special_sections = build_special_sections(search_index, document_data)
    search_corpus = build_search_corpus(search_index)
    search_results = build_search_results(search_corpus, special_sections)
    search_checks = build_search_checks(search_results)
    content_fidelity_diff = build_content_fidelity_diff(
        page_coverage_ledger=page_coverage_ledger,
        page_review=page_review,
        page_audit=page_audit,
        search_index=search_index,
        document_data=document_data,
    )
    regression_diff = build_regression_diff(
        bundle_id=bundle_id,
        baseline_bundle_id=baseline_bundle_id,
        baseline_artifacts=baseline_payload,
        page_coverage_ledger=page_coverage_ledger,
        special_sections=special_sections,
    )
    ledger_md = build_ledger_markdown(
        bundle_id=bundle_id,
        page_coverage_ledger=page_coverage_ledger,
        special_sections=special_sections,
        search_corpus=search_corpus,
        search_results=search_results,
        content_fidelity_diff=content_fidelity_diff,
        regression_diff=regression_diff,
        baseline_bundle_id=baseline_bundle_id,
    )
    return {
        "page-coverage-ledger.json": page_coverage_ledger,
        "special-sections.json": special_sections,
        "content-fidelity-diff.json": content_fidelity_diff,
        "regression-diff.json": regression_diff,
        "search-corpus.json": search_corpus,
        "search-results.json": search_results,
        "search-checks.json": search_checks,
        "ledger.md": ledger_md,
    }


def write_bundle(output_dir: Path, artifacts: dict[str, Any]) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    written_paths: list[Path] = []
    for filename, artifact in artifacts.items():
        path = output_dir / filename
        if filename.endswith(".json"):
            path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        else:
            path.write_text(str(artifact), encoding="utf-8")
        written_paths.append(path)
    return written_paths


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build an offline R2 audit bundle from data/generated outputs.")
    parser.add_argument("--bundle-id", default=default_bundle_id(), help="Target bundle id under data/research/pdf-web-audit/")
    parser.add_argument("--baseline-bundle-id", default=None, help="Optional baseline bundle id for regression comparison")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    bundle_id = str(args.bundle_id)
    baseline_bundle_id = str(args.baseline_bundle_id) if args.baseline_bundle_id else None
    if baseline_bundle_id is None and bundle_id.endswith("-r2"):
        baseline_bundle_id = bundle_id[: -len("-r2")]

    baseline_dir = RESEARCH_DIR / baseline_bundle_id if baseline_bundle_id else None
    baseline_artifacts = load_baseline_artifacts(baseline_dir)
    artifacts = build_bundle_artifacts(
        bundle_id=bundle_id,
        inventory=load_generated_json("pdf-inventory.json"),
        page_review=load_generated_json("page-review.json"),
        page_audit=load_generated_json("page-audit-report.json"),
        search_index=load_generated_json("search-index.json"),
        document_data=load_generated_json("document-data.json"),
        baseline_artifacts=baseline_artifacts,
        baseline_bundle_id=baseline_bundle_id,
    )
    output_dir = RESEARCH_DIR / bundle_id
    write_bundle(output_dir, artifacts)
    print_json_summary(
        "build-r2-audit-bundle",
        {
            "bundleId": bundle_id,
            "targetDir": str(output_dir),
            "artifactCount": len(artifacts),
            "baselineBundleId": baseline_bundle_id,
            "baselineFound": bool(baseline_artifacts),
        },
    )


if __name__ == "__main__":
    main()
