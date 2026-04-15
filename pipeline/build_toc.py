from __future__ import annotations

import re
from typing import Any

from .common import (
    clean_title,
    ensure_unique_slug,
    extract_page_text,
    load_config,
    load_generated_json,
    normalize_bookmark_title,
    open_pdf,
    print_json_summary,
    slugify,
    write_json,
)


LEVEL2_PART_RE = re.compile(r"^(제\s*[\d-]+\s*편)\s*(.+)$")
LEVEL3_CHAPTER_RE = re.compile(r"^(제\s*\d+\s*장)\s*(.+)$")
LEVEL4_SECTION_RE = re.compile(r"^(제\s*\d+\s*절)\s*(.+)$")
TOC_MARKER_RE = re.compile(r"목\s*차")


def build_outline_ranges(entries: list[dict[str, Any]], page_count: int) -> list[dict[str, Any]]:
    ranged: list[dict[str, Any]] = []
    for index, entry in enumerate(entries):
        page_end = page_count
        for candidate in entries[index + 1 :]:
            if int(candidate["level"]) <= int(entry["level"]):
                page_end = int(candidate["pageStart"]) - 1
                break
        ranged.append({**entry, "pageEnd": max(int(entry["pageStart"]), page_end)})
    return ranged


def resolve_range_end_label(
    label_by_page: dict[int, str | None],
    *,
    page_start: int,
    page_end: int,
) -> str | None:
    for page_number in range(int(page_end), int(page_start) - 1, -1):
        page_label = label_by_page.get(page_number)
        if page_label:
            return page_label
    return None


def split_label_title(value: str, pattern: re.Pattern[str]) -> tuple[str, str]:
    match = pattern.match(value)
    if not match:
        return value, value
    label = clean_title(match.group(1))
    title = clean_title(match.group(2))
    return label, f"{label} {title}".strip()


def detect_toc_pages(document: Any, inventory: dict[str, Any], *, scan_limit: int) -> list[int]:
    first_toc_page: int | None = None
    for page_number in range(1, min(document.page_count, scan_limit) + 1):
        text = extract_page_text(document.load_page(page_number - 1))
        if TOC_MARKER_RE.search(text):
            first_toc_page = page_number
            break

    if first_toc_page is None:
        return []

    toc_pages: list[int] = []
    for page in inventory.get("pages", []):
        page_number = int(page["pageNumber"])
        if page_number < first_toc_page:
            continue
        if page.get("pageKind") != "frontmatter":
            break
        toc_pages.append(page_number)

    return toc_pages


def build_synthetic_parts(
    *,
    page_count: int,
    toc_pages: list[int],
    level1_entries: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    frontmatter_chapters = [
        {
            "id": "cover-and-masthead",
            "slug": "cover-and-masthead",
            "label": "전면부",
            "title": "표지 및 발간정보",
            "fullTitle": "표지 및 발간정보",
            "pageLabelStart": None,
            "pageLabelEnd": None,
            "pageStart": 1,
            "pageEnd": 4,
            "items": [],
            "supplements": [],
        }
    ]

    preface = level1_entries.get("머리말")
    if preface:
        frontmatter_chapters.append(
            {
                "id": "front-preface",
                "slug": "front-preface",
                "label": "머리말",
                "title": "머리말",
                "fullTitle": "머리말",
                "pageLabel": preface.get("pageLabelStart"),
                "pageLabelStart": preface.get("pageLabelStart"),
                "pageLabelEnd": preface.get("pageLabelEnd"),
                "pageStart": preface["pageStart"],
                "pageEnd": preface["pageEnd"],
                "items": [],
                "supplements": [],
            }
        )

    notes = level1_entries.get("일러두기")
    if notes:
        frontmatter_chapters.append(
            {
                "id": "front-notes",
                "slug": "front-notes",
                "label": "일러두기",
                "title": "일러두기",
                "fullTitle": "일러두기",
                "pageLabel": notes.get("pageLabelStart"),
                "pageLabelStart": notes.get("pageLabelStart"),
                "pageLabelEnd": notes.get("pageLabelEnd"),
                "pageStart": notes["pageStart"],
                # Keep front-notes bounded before the detected TOC pages so reader/search
                # content does not absorb the separate 목차 spread.
                "pageEnd": min(notes["pageEnd"], (toc_pages[0] - 1) if toc_pages else notes["pageEnd"]),
                "items": [],
                "supplements": [],
            }
        )

    synthetic_parts = [
        {
            "id": "frontmatter",
            "label": "전면부",
            "title": "전면부",
            "fullTitle": "전면부",
            "pageStart": 1,
            "pageEnd": (toc_pages[0] - 1) if toc_pages else 12,
            "chapters": frontmatter_chapters,
        }
    ]

    editorial = level1_entries.get("심판편람편찬위원")
    if editorial:
        synthetic_parts.append(
            {
                "id": "backmatter",
                "label": "후면부",
                "title": "후면부",
                "fullTitle": "후면부",
                "pageStart": editorial["pageStart"],
                "pageEnd": page_count,
                "chapters": [
                    {
                        "id": "editorial-board",
                        "slug": "editorial-board",
                        "label": "편찬위원",
                        "title": "심판편람편찬위원",
                        "fullTitle": "심판편람편찬위원",
                        "pageLabel": editorial.get("pageLabelStart"),
                        "pageLabelStart": editorial.get("pageLabelStart"),
                        "pageLabelEnd": editorial.get("pageLabelEnd"),
                        "pageStart": editorial["pageStart"],
                        "pageEnd": page_count,
                        "items": [],
                        "supplements": [],
                    }
                ],
            }
        )

    return synthetic_parts


def build_reader_parts(
    ranged_entries: list[dict[str, Any]],
    *,
    slug_max_length: int,
) -> list[dict[str, Any]]:
    seen_part_slugs: set[str] = set()
    seen_chapter_slugs: set[str] = set()
    seen_section_slugs: set[str] = set()
    parts: list[dict[str, Any]] = []

    body_parts = [entry for entry in ranged_entries if entry["level"] == 2]
    chapters_by_parent = {
        part["index"]: [
            entry
            for entry in ranged_entries
            if entry["level"] == 3 and entry.get("parentIndex") == part["index"]
        ]
        for part in body_parts
    }
    sections_by_parent = {
        chapter["index"]: [
            entry
            for entry in ranged_entries
            if entry["level"] == 4 and entry.get("parentIndex") == chapter["index"]
        ]
        for chapter in [entry for entry in ranged_entries if entry["level"] == 3]
    }

    for part_entry in body_parts:
        part_label, full_title = split_label_title(part_entry["title"], LEVEL2_PART_RE)
        part_slug = ensure_unique_slug(
            slugify(full_title, max_length=slug_max_length),
            seen_part_slugs,
            max_length=slug_max_length,
        )
        part = {
            "id": part_slug,
            "label": part_label,
            "title": clean_title(full_title[len(part_label) :]) if full_title.startswith(part_label) else full_title,
            "fullTitle": full_title,
            "pageLabel": part_entry.get("pageLabelStart"),
            "pageLabelStart": part_entry.get("pageLabelStart"),
            "pageLabelEnd": part_entry.get("pageLabelEnd"),
            "pageStart": part_entry["pageStart"],
            "pageEnd": part_entry["pageEnd"],
            "chapters": [],
        }

        for chapter_entry in chapters_by_parent.get(part_entry["index"], []):
            chapter_label, chapter_full_title = split_label_title(chapter_entry["title"], LEVEL3_CHAPTER_RE)
            chapter_slug = ensure_unique_slug(
                slugify(chapter_full_title, max_length=slug_max_length),
                seen_chapter_slugs,
                max_length=slug_max_length,
            )
            chapter = {
                "id": chapter_slug,
                "slug": chapter_slug,
                "label": chapter_label,
                "title": clean_title(chapter_full_title[len(chapter_label) :])
                if chapter_full_title.startswith(chapter_label)
                else chapter_full_title,
                "fullTitle": chapter_full_title,
                "pageLabel": chapter_entry.get("pageLabelStart"),
                "pageLabelStart": chapter_entry.get("pageLabelStart"),
                "pageLabelEnd": chapter_entry.get("pageLabelEnd"),
                "pageStart": chapter_entry["pageStart"],
                "pageEnd": chapter_entry["pageEnd"],
                "items": [],
                "supplements": [],
            }

            for section_entry in sections_by_parent.get(chapter_entry["index"], []):
                section_label, section_full_title = split_label_title(section_entry["title"], LEVEL4_SECTION_RE)
                section_slug = ensure_unique_slug(
                    slugify(section_full_title, max_length=slug_max_length),
                    seen_section_slugs,
                    max_length=slug_max_length,
                )
                chapter["items"].append(
                    {
                        "id": section_slug,
                        "sectionId": section_slug,
                        "label": section_label,
                        "title": clean_title(section_full_title[len(section_label) :])
                        if section_full_title.startswith(section_label)
                        else section_full_title,
                        "fullTitle": section_full_title,
                        "pageLabel": section_entry.get("pageLabelStart"),
                        "pageLabelStart": section_entry.get("pageLabelStart"),
                        "pageLabelEnd": section_entry.get("pageLabelEnd"),
                        "pageStart": section_entry["pageStart"],
                        "pageEnd": section_entry["pageEnd"],
                    }
                )

            part["chapters"].append(chapter)

        parts.append(part)

    return parts


def main() -> None:
    config = load_config()
    inventory = load_generated_json("pdf-inventory.json")
    outline = load_generated_json("outline.json")
    document = open_pdf(config)
    slug_max_length = int(config.get("slugMaxLength", 80))
    ranged_entries = build_outline_ranges(outline["entries"], inventory["meta"]["pageCount"])
    label_by_page = {
        int(page["pageNumber"]): page.get("pageLabel")
        for page in inventory.get("pages", [])
    }
    for entry in ranged_entries:
        entry["pageLabelEnd"] = resolve_range_end_label(
            label_by_page,
            page_start=int(entry["pageStart"]),
            page_end=int(entry["pageEnd"]),
        )

    level1_entries = {
        normalize_bookmark_title(entry["title"]): entry
        for entry in ranged_entries
        if entry["level"] == 1
    }
    toc_pages = detect_toc_pages(document, inventory, scan_limit=int(config.get("tocScanPageLimit", 40)))
    parts = build_synthetic_parts(
        page_count=inventory["meta"]["pageCount"],
        toc_pages=toc_pages,
        level1_entries=level1_entries,
    )
    parts.extend(build_reader_parts(ranged_entries, slug_max_length=slug_max_length))
    chapter_count = sum(len(part["chapters"]) for part in parts)
    item_count = sum(len(chapter.get("items", [])) for part in parts for chapter in part["chapters"])

    payload = {
        "meta": {
            "title": config["documentTitle"],
            "partCount": len(parts),
            "chapterCount": chapter_count,
            "itemCount": item_count,
            "supplementCount": 0,
            "level2Count": outline["meta"].get("level2Count", 0),
            "level3Count": outline["meta"].get("level3Count", 0),
            "level4Count": outline["meta"].get("level4Count", 0),
            "outlineCount": outline["meta"].get("entryCount", 0),
            "tocPages": toc_pages,
        },
        "parts": parts,
    }
    target = write_json("toc.json", payload)
    print_json_summary(
        "toc",
        {
            "target": str(target),
            "partCount": len(parts),
            "tocPageCount": len(toc_pages),
        },
    )


if __name__ == "__main__":
    main()
