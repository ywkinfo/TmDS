from __future__ import annotations

from datetime import UTC, datetime
from html import escape
import re
from pathlib import Path
from typing import Any

import pymupdf

from .common import (
    GENERATED_DIR,
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


TABLE_CELL_SEPARATOR_RE = re.compile(r"\s+\|\s+")
TABLE_BODY_FIRST_CELL_RE = re.compile(r"^(?:\d{2,4}|[A-Z]{1,6}|[①-⑳⑴-⑽㈎-㈞ⓅⓊⒹⒺⓉⓈ])$")
SPECIAL_INLINE_HEADING_RE = re.compile(r"^(?:[\[【].+[】\]]|<\s*.+\s*>)$")


def inline_heading_to_html(paragraph: str) -> str:
    return f'<h4 class="reader-inline-heading">{escape(paragraph)}</h4>'


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
        compact_title = "".join(title.split())

        for end in range(max_probe, min_probe - 1, -1):
            candidate = value[:end].rstrip()
            normalized_candidate = normalize_bookmark_title(candidate)
            compact_candidate = "".join(normalized_candidate.split())
            if normalized_candidate == title or compact_candidate == compact_title:
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


def cluster_positions(values: list[float], *, tolerance: float) -> list[float]:
    if not values:
        return []
    ordered = sorted(float(value) for value in values)
    clusters: list[list[float]] = [[ordered[0]]]
    for value in ordered[1:]:
        if abs(value - clusters[-1][-1]) <= tolerance:
            clusters[-1].append(value)
        else:
            clusters.append([value])
    return [sum(cluster) / len(cluster) for cluster in clusters]


def build_source_line_bands(source_lines: list[dict[str, Any]], *, tolerance: float = 3.0) -> list[dict[str, Any]]:
    ordered_lines = sorted(source_lines, key=lambda line: (float(line["bbox"][1]), float(line["bbox"][0])))
    bands: list[dict[str, Any]] = []
    for line in ordered_lines:
        top = float(line["bbox"][1])
        bottom = float(line["bbox"][3])
        if bands and top <= float(bands[-1]["bottom"]) + tolerance:
            bands[-1]["lines"].append(line)
            bands[-1]["bottom"] = max(float(bands[-1]["bottom"]), bottom)
        else:
            bands.append({"top": top, "bottom": bottom, "lines": [line]})
    return bands


def band_column_cluster_count(lines: list[dict[str, Any]]) -> int:
    lefts = [float(line["bbox"][0]) for line in lines]
    return len(cluster_positions(lefts, tolerance=18.0))


def band_text_content(band: dict[str, Any]) -> str:
    return " ".join(str(line.get("text", "")).strip() for line in band["lines"]).strip()


def is_table_continuation_band(
    band: dict[str, Any],
    *,
    current_left: float,
    current_right: float,
) -> bool:
    band_left = min(float(line["bbox"][0]) for line in band["lines"])
    band_right = max(float(line["bbox"][2]) for line in band["lines"])
    width = max(1.0, current_right - current_left)
    band_width = max(1.0, band_right - band_left)
    cluster_count = band_column_cluster_count(band["lines"])
    band_center = (band_left + band_right) / 2.0
    current_center = (current_left + current_right) / 2.0
    text = band_text_content(band)
    short_band = len(text) <= 48 and band_width <= max(180.0, width * 0.5)

    return (
        (
            cluster_count == 1
            and band_left >= current_left - 8.0
            and band_right <= current_right + 18.0
            and band_width <= width * 0.55
        )
        or (
            cluster_count == 1
            and short_band
            and band_left >= current_left - width * 0.35
            and band_right <= current_left + width * 0.18
        )
        or (
            cluster_count == 1
            and short_band
            and band_left >= current_left - 8.0
            and band_right <= current_left + width * 0.22
        )
        or (
            cluster_count == 1
            and short_band
            and abs(band_center - current_center) <= max(48.0, width * 0.2)
        )
        or (
            cluster_count == 1
            and band_left >= current_left + width * 0.12
            and band_right <= current_right + 12.0
            and band_width >= width * 0.35
        )
    )


def detect_dense_form_region(
    bands: list[dict[str, Any]],
    *,
    page_width: float,
    table_like_indices: list[int],
) -> dict[str, Any] | None:
    if len(table_like_indices) < 4:
        return None

    start_band_index = table_like_indices[0]
    end_band_index = table_like_indices[-1]
    included_bands = bands[start_band_index : end_band_index + 1]
    current_left = min(float(line["bbox"][0]) for band in included_bands for line in band["lines"])
    current_right = max(float(line["bbox"][2]) for band in included_bands for line in band["lines"])

    for index in range(start_band_index, end_band_index + 1):
        if index in table_like_indices:
            continue
        if not is_table_continuation_band(
            bands[index],
            current_left=current_left,
            current_right=current_right,
        ):
            return None

    while start_band_index > 0:
        previous_band = bands[start_band_index - 1]
        previous_left = min(float(line["bbox"][0]) for line in previous_band["lines"])
        previous_right = max(float(line["bbox"][2]) for line in previous_band["lines"])
        previous_width = previous_right - previous_left
        previous_center = (previous_left + previous_right) / 2.0
        current_center = (current_left + current_right) / 2.0
        previous_text = band_text_content(previous_band)
        previous_gap = float(bands[start_band_index]["top"]) - float(previous_band["bottom"])
        if (
            previous_gap <= 32.0
            and previous_text
            and len(previous_text) <= 48
            and previous_width <= max(180.0, (current_right - current_left) * 0.5)
            and abs(previous_center - current_center) <= max(48.0, (current_right - current_left) * 0.2)
        ):
            start_band_index -= 1
            continue
        break

    while end_band_index + 1 < len(bands):
        next_band = bands[end_band_index + 1]
        next_gap = float(next_band["top"]) - float(bands[end_band_index]["bottom"])
        if next_gap > 50.0:
            break
        if not is_table_continuation_band(
            next_band,
            current_left=current_left,
            current_right=current_right,
        ):
            break
        end_band_index += 1

    included_bands = bands[start_band_index : end_band_index + 1]
    line_indices = {
        int(line["index"])
        for band in included_bands
        for line in band["lines"]
        if line.get("index") is not None
    }
    left = min(float(line["bbox"][0]) for band in included_bands for line in band["lines"])
    top = min(float(line["bbox"][1]) for band in included_bands for line in band["lines"])
    right = max(float(line["bbox"][2]) for band in included_bands for line in band["lines"])
    bottom = max(float(line["bbox"][3]) for band in included_bands for line in band["lines"])

    return {
        "id": 1,
        "lineIndices": line_indices,
        "bbox": [
            max(0.0, left - 12.0),
            max(0.0, top - 12.0),
            min(page_width, right + 12.0),
            bottom + 12.0,
        ],
    }


def detect_table_regions(page_review: dict[str, Any], *, page_width: float) -> list[dict[str, Any]]:
    source_lines = list(page_review.get("sourceLines", []))
    if not source_lines:
        return []

    bands = build_source_line_bands(source_lines)
    table_like_indices = [
        index
        for index, band in enumerate(bands)
        if len(band["lines"]) >= 2 and band_column_cluster_count(band["lines"]) >= 2
    ]
    if not table_like_indices:
        return []

    dense_form_region = detect_dense_form_region(
        bands,
        page_width=page_width,
        table_like_indices=table_like_indices,
    )
    if dense_form_region is not None:
        return [dense_form_region]

    groups: list[tuple[int, int]] = []
    start_index = table_like_indices[0]
    end_index = table_like_indices[0]
    for index in table_like_indices[1:]:
        previous_band = bands[end_index]
        current_band = bands[index]
        included_bands = bands[start_index : end_index + 1]
        current_left = min(float(line["bbox"][0]) for band in included_bands for line in band["lines"])
        current_right = max(float(line["bbox"][2]) for band in included_bands for line in band["lines"])
        intermediate_bands = bands[end_index + 1 : index]
        intermediates_ok = all(
            is_table_continuation_band(
                band,
                current_left=current_left,
                current_right=current_right,
            )
            for band in intermediate_bands
        )
        effective_bottom = (
            float(intermediate_bands[-1]["bottom"]) if intermediate_bands else float(previous_band["bottom"])
        )

        if float(current_band["top"]) - effective_bottom <= 42.0 and intermediates_ok:
            end_index = index
            continue
        groups.append((start_index, end_index))
        start_index = index
        end_index = index
    groups.append((start_index, end_index))

    regions: list[dict[str, Any]] = []
    for group_index, (start_band_index, end_band_index) in enumerate(groups, start=1):
        if start_band_index > 0:
            previous_band = bands[start_band_index - 1]
            previous_lines = previous_band["lines"]
            if len(previous_lines) == 1:
                previous_text = str(previous_lines[0]["text"]).strip()
                if previous_text.startswith("【") or previous_text.startswith("["):
                    start_band_index -= 1

        while start_band_index > 0:
            current_included_bands = bands[start_band_index : end_band_index + 1]
            current_left = min(float(line["bbox"][0]) for band in current_included_bands for line in band["lines"])
            current_right = max(float(line["bbox"][2]) for band in current_included_bands for line in band["lines"])
            current_top = min(float(line["bbox"][1]) for band in current_included_bands for line in band["lines"])

            previous_band = bands[start_band_index - 1]
            previous_bottom = float(previous_band["bottom"])
            previous_gap = current_top - previous_bottom
            previous_lines = previous_band["lines"]
            previous_left = min(float(line["bbox"][0]) for line in previous_lines)
            previous_right = max(float(line["bbox"][2]) for line in previous_lines)
            previous_width = previous_right - previous_left
            previous_center = (previous_left + previous_right) / 2.0
            current_center = (current_left + current_right) / 2.0

            if (
                previous_gap <= 24.0
                and len(previous_lines) <= 2
                and previous_width <= (current_right - current_left) * 0.65
                and abs(previous_center - current_center) <= 36.0
            ):
                start_band_index -= 1
                continue
            break

        while end_band_index + 1 < len(bands):
            current_included_bands = bands[start_band_index : end_band_index + 1]
            left = min(float(line["bbox"][0]) for band in current_included_bands for line in band["lines"])
            right = max(float(line["bbox"][2]) for band in current_included_bands for line in band["lines"])
            width = max(1.0, right - left)
            next_band = bands[end_band_index + 1]
            next_gap = float(next_band["top"]) - float(bands[end_band_index]["bottom"])
            next_left = min(float(line["bbox"][0]) for line in next_band["lines"])
            next_right = max(float(line["bbox"][2]) for line in next_band["lines"])

            if next_gap <= 24.0 and is_table_continuation_band(
                next_band,
                current_left=left,
                current_right=right,
            ):
                end_band_index += 1
                continue

            # Include wrapped continuation lines that sit in the right half of the table,
            # which commonly appear as the tail of the last row in multi-column comparison tables.
            if next_gap <= 18.0 and next_left >= left + width * 0.45 and next_right <= right + 12.0:
                end_band_index += 1
                continue
            break

        included_bands = bands[start_band_index : end_band_index + 1]
        line_indices = {
            int(line["index"])
            for band in included_bands
            for line in band["lines"]
            if line.get("index") is not None
        }
        left = min(float(line["bbox"][0]) for band in included_bands for line in band["lines"])
        top = min(float(line["bbox"][1]) for band in included_bands for line in band["lines"])
        right = max(float(line["bbox"][2]) for band in included_bands for line in band["lines"])
        bottom = max(float(line["bbox"][3]) for band in included_bands for line in band["lines"])
        regions.append(
            {
                "id": group_index,
                "lineIndices": line_indices,
                "bbox": [
                    max(0.0, left - 12.0),
                    max(0.0, top - 12.0),
                    min(page_width, right + 12.0),
                    bottom + 12.0,
                ],
            }
        )

    return regions


def render_table_region_images(
    document: pymupdf.Document,
    page_review_entries: list[dict[str, Any]],
) -> dict[int, list[dict[str, Any]]]:
    target_dir = GENERATED_DIR / "images" / "table-crops"
    if target_dir.exists():
        for path in target_dir.rglob("*"):
            if path.is_file():
                path.unlink()
    target_dir.mkdir(parents=True, exist_ok=True)
    region_map: dict[int, list[dict[str, Any]]] = {}

    for entry in page_review_entries:
        page_number = int(entry["pageNumber"])
        page = document.load_page(page_number - 1)
        page_width = float(page.rect.width)
        page_height = float(page.rect.height)
        regions = detect_table_regions(entry, page_width=page_width)
        if not regions:
            continue

        rendered_regions: list[dict[str, Any]] = []
        for region in regions:
            left, top, right, bottom = region["bbox"]
            clip = pymupdf.Rect(left, top, right, min(bottom, page_height))
            pixmap = page.get_pixmap(matrix=pymupdf.Matrix(2, 2), clip=clip, alpha=False)
            filename = f"{page_number:04d}-{int(region['id'])}.png"
            target_path = target_dir / filename
            target_path.write_bytes(pixmap.tobytes("png"))
            rendered_regions.append(
                {
                    **region,
                    "relativePath": f"images/table-crops/{filename}",
                }
            )

        region_map[page_number] = rendered_regions

    return region_map


def collect_range_blocks(
    *,
    page_start: int,
    page_end: int,
    page_review_map: dict[int, dict[str, Any]],
    page_image_map: dict[int, list[str]],
    table_region_map: dict[int, list[dict[str, Any]]],
    trim_titles: tuple[str, ...] = (),
) -> list[dict[str, Any]]:
    if int(page_end) < int(page_start):
        return []

    blocks: list[dict[str, Any]] = []
    first_paragraph_emitted = False

    for page_number in range(int(page_start), int(page_end) + 1):
        page_review = page_review_map.get(page_number, {})
        table_regions = table_region_map.get(page_number, [])
        inserted_region_ids: set[int] = set()
        ordered_region_ids = [int(region["id"]) for region in table_regions]
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
                and blocks
                and blocks[-1]["type"] == "paragraph"
            ):
                blocks[-1]["text"] = f"{blocks[-1]['text']} {paragraph}".strip()
                continue

            matched_region_id: int | None = None
            source_line_indices = {int(index) for index in paragraph_entry.get("sourceLines", [])}
            for region in table_regions:
                if source_line_indices and source_line_indices.intersection(region["lineIndices"]):
                    matched_region_id = int(region["id"])
                    break
            if matched_region_id is None and not source_line_indices and len(table_regions) == 1:
                if str(paragraph_entry.get("kind") or "") == "table/form":
                    matched_region_id = int(table_regions[0]["id"])

            if matched_region_id is not None and matched_region_id not in inserted_region_ids:
                region = next(region for region in table_regions if int(region["id"]) == matched_region_id)
                blocks.append(
                    {
                        "type": "table-image",
                        "relativePath": str(region["relativePath"]),
                    }
                )
                inserted_region_ids.add(matched_region_id)

            suppress_html = matched_region_id is not None
            if (
                not suppress_html
                and table_regions
                and str(paragraph_entry.get("kind") or "") == "table/form"
                and inserted_region_ids
            ):
                current_region_id = max(inserted_region_ids)
                if any(region_id > current_region_id for region_id in ordered_region_ids):
                    suppress_html = True

            blocks.append(
                {
                    "type": "paragraph",
                    "text": paragraph,
                    "kind": (
                        "body"
                        if table_regions and matched_region_id is None and str(paragraph_entry.get("kind") or "") == "table/form"
                        else str(paragraph_entry.get("kind") or "body")
                    ),
                    "suppressHtml": suppress_html,
                }
            )
            first_paragraph_emitted = True

        for relative_path in page_image_map.get(page_number, []):
            blocks.append(
                {
                    "type": "image",
                    "relativePath": relative_path,
                }
            )

    return blocks


def render_content_blocks(
    *,
    blocks: list[dict[str, Any]],
    image_alt: str,
) -> tuple[str, str, int]:
    html_parts: list[str] = []
    text_parts: list[str] = []
    image_count = 0
    pending_table_rows: list[list[str]] = []

    def flush_pending_table() -> None:
        nonlocal pending_table_rows
        if not pending_table_rows:
            return
        html_parts.append(table_rows_to_html(pending_table_rows))
        pending_table_rows = []

    for block in blocks:
        if block.get("type") in {"image", "table-image"}:
            flush_pending_table()
            html_parts.append(image_to_html(str(block["relativePath"]), image_alt))
            if block.get("type") == "image":
                image_count += 1
            continue

        paragraph = str(block.get("text", "")).strip()
        if not paragraph:
            continue
        text_parts.append(paragraph)

        if bool(block.get("suppressHtml")):
            continue

        if is_table_paragraph_entry(block, paragraph):
            pending_table_rows.append(split_table_cells(paragraph))
            continue

        flush_pending_table()
        if str(block.get("kind") or "") == "heading" and SPECIAL_INLINE_HEADING_RE.match(paragraph):
            html_parts.append(inline_heading_to_html(paragraph))
            continue
        html_parts.append(paragraph_to_html(paragraph))

    flush_pending_table()
    return "".join(html_parts), "\n\n".join(text_parts).strip(), image_count


def split_table_cells(paragraph: str) -> list[str]:
    cells = [cell.strip() for cell in TABLE_CELL_SEPARATOR_RE.split(paragraph.strip())]
    return [cell for cell in cells if cell]


def is_table_paragraph_entry(paragraph_entry: dict[str, Any], paragraph: str) -> bool:
    return str(paragraph_entry.get("kind")) == "table/form" and len(split_table_cells(paragraph)) >= 2


def detect_table_header_row_count(rows: list[list[str]]) -> int:
    header_count = 0

    for row in rows:
        first_cell = next((cell for cell in row if cell.strip()), "")
        if not first_cell:
            break
        if TABLE_BODY_FIRST_CELL_RE.match(first_cell.strip()):
            break
        header_count += 1

    return header_count


def table_rows_to_html(rows: list[list[str]]) -> str:
    if not rows:
        return ""

    column_count = max(len(row) for row in rows)
    normalized_rows = [row + [""] * (column_count - len(row)) for row in rows]
    header_row_count = detect_table_header_row_count(normalized_rows)

    html_parts = ['<table class="reader-synthetic-table">']
    if header_row_count > 0:
        html_parts.append("<thead>")
        for row in normalized_rows[:header_row_count]:
            html_parts.append("<tr>")
            html_parts.extend(f"<th>{escape(cell)}</th>" for cell in row)
            html_parts.append("</tr>")
        html_parts.append("</thead>")

    body_rows = normalized_rows[header_row_count:]
    html_parts.append("<tbody>")
    for row in body_rows:
        html_parts.append("<tr>")
        html_parts.extend(f"<td>{escape(cell)}</td>" for cell in row)
        html_parts.append("</tr>")
    html_parts.append("</tbody></table>")
    return "".join(html_parts)


def render_range_html(
    *,
    page_start: int,
    page_end: int,
    page_review_map: dict[int, dict[str, Any]],
    page_image_map: dict[int, list[str]],
    table_region_map: dict[int, list[dict[str, Any]]],
    image_alt: str,
    trim_titles: tuple[str, ...] = (),
) -> tuple[str, str, int]:
    blocks = collect_range_blocks(
        page_start=page_start,
        page_end=page_end,
        page_review_map=page_review_map,
        page_image_map=page_image_map,
        table_region_map=table_region_map,
        trim_titles=trim_titles,
    )
    return render_content_blocks(blocks=blocks, image_alt=image_alt)


def split_paragraph_by_section_titles(
    paragraph: str,
    ordered_titles: list[str],
) -> list[dict[str, str]]:
    title_patterns = [
        (
            title,
            re.compile(re.escape(title).replace(r"\ ", r"[\s·ㆍ․]*")),
        )
        for title in ordered_titles
    ]
    remaining = paragraph
    parts: list[dict[str, str]] = []

    while remaining:
        next_match: tuple[int, int, str] | None = None
        for title, pattern in title_patterns:
            match = pattern.search(remaining)
            if match is None:
                continue
            if (
                next_match is None
                or match.start() < next_match[0]
                or (match.start() == next_match[0] and len(title) > len(next_match[2]))
            ):
                next_match = (match.start(), match.end(), title)

        if next_match is None:
            text = remaining.strip()
            if text:
                parts.append({"type": "text", "value": text})
            break

        start, end, title = next_match
        if start > 0:
            leading_text = remaining[:start].strip()
            if leading_text:
                parts.append({"type": "text", "value": leading_text})
        parts.append({"type": "heading", "value": title})
        remaining = remaining[end:]

    return parts


def segment_blocks_by_section_titles(
    *,
    blocks: list[dict[str, Any]],
    items: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    ordered_titles = [normalize_bookmark_title(item["fullTitle"]) for item in items]
    section_id_by_title = {
        normalize_bookmark_title(item["fullTitle"]): str(item["sectionId"])
        for item in items
    }
    segmented_blocks: dict[str, list[dict[str, Any]]] = {"overview": []}
    segmented_blocks.update({str(item["sectionId"]): [] for item in items})
    current_bucket = "overview"

    for block in blocks:
        if block.get("type") in {"image", "table-image"}:
            segmented_blocks[current_bucket].append(block)
            continue

        paragraph = str(block.get("text", "")).strip()
        if not paragraph:
            continue

        parts = split_paragraph_by_section_titles(paragraph, ordered_titles)
        if not parts:
            continue

        for part in parts:
            if part["type"] == "heading":
                current_bucket = section_id_by_title.get(part["value"], current_bucket)
                continue
            text = part["value"].strip()
            if not text:
                continue
            segmented_blocks[current_bucket].append(
                {
                    **block,
                    "text": text,
                }
            )

    return segmented_blocks


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
    table_region_map = render_table_region_images(document, page_review_entries)

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
            chapter_title = normalize_bookmark_title(chapter["fullTitle"])
            part_title = normalize_bookmark_title(part["fullTitle"])

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

            segmented_blocks: dict[str, list[dict[str, Any]]] | None = None
            if items:
                chapter_blocks = collect_range_blocks(
                    page_start=int(chapter["pageStart"]),
                    page_end=int(chapter["pageEnd"]),
                    page_review_map=page_review_map,
                    page_image_map=page_image_map,
                    table_region_map=table_region_map,
                    trim_titles=(chapter_title, part_title),
                )
                segmented_blocks = segment_blocks_by_section_titles(
                    blocks=chapter_blocks,
                    items=items,
                )
                overview_html, overview_text, overview_image_count = render_content_blocks(
                    blocks=segmented_blocks["overview"],
                    image_alt=chapter_title,
                )
            else:
                overview_html, overview_text, overview_image_count = render_range_html(
                    page_start=int(chapter["pageStart"]),
                    page_end=int(overview_page_end),
                    page_review_map=page_review_map,
                    page_image_map=page_image_map,
                    table_region_map=table_region_map,
                    image_alt=chapter_title,
                    trim_titles=(chapter_title, part_title),
                )

            chapter_has_image = chapter_has_image or overview_image_count > 0
            chapter_image_count += overview_image_count
            cleaned_overview_text = trim_leading_heading_noise(
                overview_text or chapter_title,
                chapter_title,
                part_title,
            )

            overview_excerpt = make_excerpt(
                cleaned_overview_text or chapter_title,
                limit=220,
            )
            search_index.append(
                {
                    "id": f'{chapter["slug"]}-overview',
                    "chapterSlug": chapter["slug"],
                    "chapterTitle": chapter_title,
                    "sectionId": "overview",
                    "sectionTitle": "개요",
                    "text": cleaned_overview_text or chapter_title,
                    "excerpt": overview_excerpt,
                    "entryType": "overview",
                    "partTitle": part_title,
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
                if segmented_blocks is not None:
                    section_html, section_text, section_image_count = render_content_blocks(
                        blocks=segmented_blocks.get(str(item["sectionId"]), []),
                        image_alt=section_title,
                    )
                else:
                    section_html, section_text, section_image_count = render_range_html(
                        page_start=int(item["pageStart"]),
                        page_end=int(item["pageEnd"]),
                        page_review_map=page_review_map,
                        page_image_map=page_image_map,
                        table_region_map=table_region_map,
                        image_alt=section_title,
                        trim_titles=(section_title, chapter_title, part_title),
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
                    chapter_title,
                    part_title,
                )
                categories = classify_entry(
                    {
                        "sectionTitle": section_title,
                        "partTitle": part_title,
                    }
                )
                search_index.append(
                    {
                        "id": item["sectionId"],
                        "chapterSlug": chapter["slug"],
                        "chapterTitle": chapter_title,
                        "sectionId": item["sectionId"],
                        "sectionTitle": section_title,
                        "text": cleaned_section_text or section_title,
                        "excerpt": make_excerpt(cleaned_section_text or section_title),
                        "entryType": "item",
                        "partTitle": part_title,
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
            overview_fallback_text = cleaned_overview_text.strip()
            chapter_overview_fallback_html = (
                paragraph_to_html(overview_fallback_text)
                if overview_fallback_text and normalize_bookmark_title(overview_fallback_text) != chapter_title
                else ""
            )

            chapters.append(
                {
                    "id": chapter["slug"],
                    "slug": chapter["slug"],
                    "title": chapter_title,
                    "summary": chapter_summary,
                    "html": build_chapter_html(
                        chapter=chapter,
                        chapter_overview_html=overview_html or chapter_overview_fallback_html,
                        section_html_parts=section_html_parts,
                    ),
                    "hasImage": chapter_has_image,
                    "imageCount": chapter_image_count,
                    "headings": section_headings,
                    "partTitle": part_title,
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
