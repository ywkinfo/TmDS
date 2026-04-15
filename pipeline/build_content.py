from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from .common import (
    clean_title,
    load_config,
    load_generated_json,
    make_excerpt,
    normalize_bookmark_title,
    open_pdf,
    paragraph_to_html,
    print_json_summary,
    write_json,
    image_to_html,
)
from .review_layout import build_page_review_entries


def classify_entry(entry: dict[str, Any]) -> list[str]:
    title = normalize_bookmark_title(entry["sectionTitle"])
    part_title = normalize_bookmark_title(entry["partTitle"])
    haystack = f"{title} {part_title}"
    categories: list[str] = []
    rules = {
        "party": [
            "당사자",
            "청구인",
            "피청구인",
            "대리인",
            "참가인",
            "심판관",
            "특허권자",
            "상표권자",
            "사용권자",
            "권리자",
        ],
        "timing": [
            "기간",
            "시기",
            "기산",
            "만료",
            "연장",
            "정지",
            "승계",
        ],
        "evidence": [
            "증거",
            "증인",
            "감정",
            "검증",
            "문서",
            "신문",
            "심문",
            "석명",
            "사실조회",
        ],
        "criteria": [
            "요건",
            "기준",
            "판단",
            "효력",
            "효과",
            "성격",
            "범위",
            "대상",
            "원인",
            "사유",
            "유형",
            "종류",
        ],
        "case": [
            "사례",
            "판례",
            "예시",
        ],
        "procedure": [
            "절차",
            "처리",
            "진행",
            "청구",
            "신청",
            "취하",
            "송달",
            "보정",
            "접수",
            "심리",
            "심결",
            "결정",
            "기재",
            "제출",
            "통지",
            "설명회",
            "병합",
            "분리",
            "수리",
            "반려",
            "반환",
        ],
        "appendix": [
            "서식",
            "개정내용",
            "기준일 안내",
        ],
    }
    for label, needles in rules.items():
        if any(needle in haystack for needle in needles):
            categories.append(label)

    if "부 록" in part_title and "appendix" not in categories:
        categories.append("appendix")

    # Keep a stable order while avoiding duplicates.
    seen: set[str] = set()
    ordered: list[str] = []
    for category in categories:
        if category in seen:
            continue
        seen.add(category)
        ordered.append(category)
    return ordered


def format_part_intro_locator(chapter: dict[str, Any]) -> str:
    page_label = chapter.get("pageLabelStart")
    if page_label:
        return f"p.{page_label}"
    return f"PDF {chapter['pageStart']}"


def build_part_intro_content(part: dict[str, Any]) -> tuple[str, str]:
    chapter_lines = [
        f"{normalize_bookmark_title(chapter['fullTitle'])} ({format_part_intro_locator(chapter)})"
        for chapter in part.get("chapters", [])
    ]
    if not chapter_lines:
        title = normalize_bookmark_title(part["fullTitle"])
        return paragraph_to_html(title), title

    intro_text = "이 편은 다음 장으로 구성됩니다. " + " / ".join(chapter_lines)
    html = paragraph_to_html("이 편은 다음 장으로 구성됩니다.") + "".join(
        paragraph_to_html(line) for line in chapter_lines
    )
    return html, intro_text


def trim_leading_heading_noise(text: str, *titles: str) -> str:
    cleaned = text.strip()
    normalized_titles = [normalize_bookmark_title(title) for title in titles if title]

    def consume_matching_prefix(value: str, title: str) -> tuple[str, bool]:
        max_probe = min(len(value), len(title) + 12)
        min_probe = max(1, len(title) - 8)

        for end in range(max_probe, min_probe - 1, -1):
            candidate = value[:end].rstrip()
            if normalize_bookmark_title(candidate) == title:
                return value[end:].lstrip(), True
        return value, False

    changed = True
    while changed and cleaned:
        changed = False
        for title in normalized_titles:
            next_value, matched = consume_matching_prefix(cleaned, title)
            if matched:
                cleaned = next_value
                changed = True

    return cleaned


def build_page_image_map(image_manifest: dict[str, Any]) -> dict[int, list[str]]:
    page_image_map: dict[int, list[str]] = {}
    for image in image_manifest.get("images", []):
        relative_path = image.get("relativePath")
        if not relative_path:
            continue
        for page_number in image.get("pageNumbers", []):
            page_image_map.setdefault(int(page_number), []).append(str(relative_path))
    return page_image_map


def render_range_html(
    *,
    page_start: int,
    page_end: int,
    page_review_map: dict[int, dict[str, Any]],
    page_image_map: dict[int, list[str]],
    image_alt: str,
    trim_titles: tuple[str, ...] = (),
) -> tuple[str, str, int]:
    if int(page_end) < int(page_start):
        return "", "", 0

    html_parts: list[str] = []
    text_parts: list[str] = []
    image_count = 0
    first_paragraph_emitted = False

    for page_number in range(int(page_start), int(page_end) + 1):
        page_review = page_review_map.get(page_number, {})
        for paragraph_entry in page_review.get("paragraphs", []):
            paragraph = str(paragraph_entry.get("text", "")).strip()
            if not paragraph:
                continue
            if trim_titles and not first_paragraph_emitted:
                paragraph = trim_leading_heading_noise(paragraph, *trim_titles)
                if not paragraph:
                    continue
            if (
                first_paragraph_emitted
                and paragraph_entry.get("index") == 0
                and page_review.get("mergeFirstGroupWithPreviousPage")
                and text_parts
            ):
                text_parts[-1] = f"{text_parts[-1]} {paragraph}".strip()
                html_parts[-1] = paragraph_to_html(text_parts[-1])
                continue
            html_parts.append(paragraph_to_html(paragraph))
            text_parts.append(paragraph)
            first_paragraph_emitted = True

        for relative_path in page_image_map.get(page_number, []):
            html_parts.append(image_to_html(relative_path, image_alt))
            image_count += 1

    return "".join(html_parts), "\n\n".join(text_parts).strip(), image_count


def build_chapter_html(
    *,
    chapter: dict[str, Any],
    chapter_overview_html: str,
    section_html_parts: list[str],
) -> str:
    overview_title = normalize_bookmark_title(chapter["fullTitle"])
    return (
        f'<section id="overview"><h2>{overview_title}</h2>{chapter_overview_html}</section>'
        + "".join(section_html_parts)
    )


def main() -> None:
    config = load_config()
    inventory = load_generated_json("pdf-inventory.json")
    toc = load_generated_json("toc.json")
    try:
        image_manifest = load_generated_json("image-manifest.json")
    except SystemExit:
        image_manifest = {"images": []}
    document = open_pdf(config)
    page_review_entries = build_page_review_entries(document, inventory)
    page_review_map = {int(entry["pageNumber"]): entry for entry in page_review_entries}
    page_image_map = build_page_image_map(image_manifest)

    chapters: list[dict[str, Any]] = []
    search_index: list[dict[str, Any]] = []
    exploration_index: list[dict[str, Any]] = []

    for part in toc["parts"]:
        for chapter_index, chapter in enumerate(part["chapters"]):
            items = chapter.get("items", [])
            part_intro_start = int(part["pageStart"])
            part_intro_end = int(chapter["pageStart"]) - 1 if chapter_index == 0 else int(chapter["pageStart"]) - 1
            has_part_intro = chapter_index == 0 and part_intro_end >= part_intro_start
            first_item_start = items[0]["pageStart"] if items else None
            overview_page_end = (
                chapter["pageEnd"] if first_item_start is None else int(first_item_start) - 1
            )
            section_html_parts: list[str] = []
            section_headings: list[dict[str, Any]] = []
            chapter_has_image = False
            chapter_image_count = 0

            if has_part_intro:
                part_intro_html, part_intro_text = build_part_intro_content(part)
                part_intro_image_count = 0
                section_html_parts.append(
                    f'<section id="part-intro"><h3>{normalize_bookmark_title(part["fullTitle"])}</h3>{part_intro_html}</section>'
                )
                search_index.append(
                    {
                        "id": f'{chapter["slug"]}-part-intro',
                        "chapterSlug": chapter["slug"],
                        "chapterTitle": normalize_bookmark_title(chapter["fullTitle"]),
                        "sectionId": "part-intro",
                        "sectionTitle": normalize_bookmark_title(part["fullTitle"]),
                        "text": part_intro_text or normalize_bookmark_title(part["fullTitle"]),
                        "excerpt": make_excerpt(part_intro_text or normalize_bookmark_title(part["fullTitle"])),
                        "entryType": "part-intro",
                        "partTitle": normalize_bookmark_title(part["fullTitle"]),
                        "pageLabel": part.get("pageLabelStart"),
                        "pageStart": part_intro_start,
                        "pageEnd": part_intro_end,
                        "pageLabelStart": part.get("pageLabelStart"),
                        "pageLabelEnd": part.get("pageLabelEnd"),
                        "hasImage": part_intro_image_count > 0,
                        "imageCount": part_intro_image_count,
                        "categories": [],
                    }
                )
                chapter_has_image = part_intro_image_count > 0
                chapter_image_count = part_intro_image_count

            overview_html, overview_text, overview_image_count = render_range_html(
                page_start=int(chapter["pageStart"]),
                page_end=int(overview_page_end),
                page_review_map=page_review_map,
                page_image_map=page_image_map,
                image_alt=normalize_bookmark_title(chapter["fullTitle"]),
                trim_titles=(
                    normalize_bookmark_title(chapter["fullTitle"]),
                    normalize_bookmark_title(part["fullTitle"]),
                ),
            )

            chapter_has_image = chapter_has_image or overview_image_count > 0
            chapter_image_count += overview_image_count
            cleaned_overview_text = trim_leading_heading_noise(
                overview_text or normalize_bookmark_title(chapter["fullTitle"]),
                normalize_bookmark_title(chapter["fullTitle"]),
                normalize_bookmark_title(part["fullTitle"]),
            )

            overview_excerpt = make_excerpt(
                cleaned_overview_text or normalize_bookmark_title(chapter["fullTitle"]),
                limit=220,
            )
            search_index.append(
                {
                    "id": f'{chapter["slug"]}-overview',
                    "chapterSlug": chapter["slug"],
                    "chapterTitle": normalize_bookmark_title(chapter["fullTitle"]),
                    "sectionId": "overview",
                    "sectionTitle": "개요",
                    "text": cleaned_overview_text or normalize_bookmark_title(chapter["fullTitle"]),
                    "excerpt": overview_excerpt,
                    "entryType": "overview",
                    "partTitle": normalize_bookmark_title(part["fullTitle"]),
                    "pageLabel": chapter.get("pageLabelStart"),
                    "pageStart": chapter["pageStart"],
                    "pageEnd": max(chapter["pageStart"], overview_page_end),
                    "pageLabelStart": chapter.get("pageLabelStart"),
                    "pageLabelEnd": chapter.get("pageLabelStart"),
                    "hasImage": overview_image_count > 0,
                    "imageCount": overview_image_count,
                    "categories": [],
                }
            )

            for item in items:
                section_title = normalize_bookmark_title(item["fullTitle"])
                section_html, section_text, section_image_count = render_range_html(
                    page_start=int(item["pageStart"]),
                    page_end=int(item["pageEnd"]),
                    page_review_map=page_review_map,
                    page_image_map=page_image_map,
                    image_alt=normalize_bookmark_title(item["fullTitle"]),
                    trim_titles=(
                        section_title,
                        normalize_bookmark_title(chapter["fullTitle"]),
                        normalize_bookmark_title(part["fullTitle"]),
                    ),
                )
                section_html_parts.append(
                    f'<section id="{item["sectionId"]}"><h3>{section_title}</h3>{section_html}</section>'
                )
                section_headings.append(
                    {
                        "id": item["sectionId"],
                        "depth": 3,
                        "title": section_title,
                    }
                )
                chapter_has_image = chapter_has_image or section_image_count > 0
                chapter_image_count += section_image_count
                cleaned_section_text = trim_leading_heading_noise(
                    section_text or section_title,
                    section_title,
                    normalize_bookmark_title(chapter["fullTitle"]),
                    normalize_bookmark_title(part["fullTitle"]),
                )
                categories = classify_entry(
                    {
                        "sectionTitle": section_title,
                        "partTitle": normalize_bookmark_title(part["fullTitle"]),
                    }
                )
                search_index.append(
                    {
                        "id": item["sectionId"],
                        "chapterSlug": chapter["slug"],
                        "chapterTitle": normalize_bookmark_title(chapter["fullTitle"]),
                        "sectionId": item["sectionId"],
                        "sectionTitle": section_title,
                        "text": cleaned_section_text or section_title,
                        "excerpt": make_excerpt(cleaned_section_text or section_title),
                        "entryType": "item",
                        "partTitle": normalize_bookmark_title(part["fullTitle"]),
                        "pageLabel": item.get("pageLabelStart"),
                        "pageStart": item["pageStart"],
                        "pageEnd": item["pageEnd"],
                        "pageLabelStart": item.get("pageLabelStart"),
                        "pageLabelEnd": item.get("pageLabelEnd"),
                        "hasImage": section_image_count > 0,
                        "imageCount": section_image_count,
                        "categories": categories,
                    }
                )

            chapter_text = "\n\n".join(
                entry["text"]
                for entry in search_index
                if entry["chapterSlug"] == chapter["slug"] and entry["text"] and entry["entryType"] != "part-intro"
            )
            chapter_summary = make_excerpt(chapter_text or normalize_bookmark_title(chapter["fullTitle"]), limit=220)

            chapters.append(
                {
                    "id": chapter["slug"],
                    "slug": chapter["slug"],
                    "title": normalize_bookmark_title(chapter["fullTitle"]),
                    "summary": chapter_summary,
                    "html": build_chapter_html(
                        chapter=chapter,
                        chapter_overview_html=overview_html or paragraph_to_html(chapter_summary),
                        section_html_parts=section_html_parts,
                    ),
                    "hasImage": chapter_has_image,
                    "imageCount": chapter_image_count,
                    "headings": section_headings,
                    "partTitle": normalize_bookmark_title(part["fullTitle"]),
                    "pageLabel": chapter.get("pageLabelStart"),
                    "pageStart": chapter["pageStart"],
                    "pageEnd": chapter["pageEnd"],
                    "pageLabelStart": chapter.get("pageLabelStart"),
                    "pageLabelEnd": chapter.get("pageLabelEnd"),
                }
            )

    exploration_index = [
        {
            "id": entry["id"],
            "title": entry["sectionTitle"],
            "chapterTitle": entry["chapterTitle"],
            "partTitle": entry["partTitle"],
            "categories": entry["categories"],
            "pageLabel": entry["pageLabel"],
            "pageStart": entry["pageStart"],
            "pageEnd": entry["pageEnd"],
            "pageLabelStart": entry["pageLabelStart"],
            "pageLabelEnd": entry["pageLabelEnd"],
            "hasImage": entry["hasImage"],
            "excerpt": entry["excerpt"],
        }
        for entry in search_index
        if entry["entryType"] == "item" and entry["categories"]
    ]

    document_payload = {
        "meta": {
            "title": config["documentTitle"],
            "builtAt": datetime.now(UTC).isoformat(),
            "chapterCount": len(chapters),
            "pageCount": document.page_count,
            "partCount": len(toc["parts"]),
        },
        "chapters": chapters,
    }

    document_target = write_json("document-data.json", document_payload)
    search_target = write_json("search-index.json", search_index)
    exploration_target = write_json("exploration-index.json", exploration_index)
    print_json_summary(
        "content",
        {
            "documentTarget": str(document_target),
            "searchTarget": str(search_target),
            "explorationTarget": str(exploration_target),
            "chapterCount": len(chapters),
            "searchEntryCount": len(search_index),
            "explorationEntryCount": len(exploration_index),
        },
    )


if __name__ == "__main__":
    main()
