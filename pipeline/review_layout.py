from __future__ import annotations

import json
import re
import shutil
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median
from typing import Any

import pymupdf

from .common import DATA_DIR, GENERATED_DIR, extract_page_blocks, normalize_bookmark_title, normalize_line, parse_page_label_line


OVERRIDES_PATH = DATA_DIR / "research" / "paragraph-overrides.json"
REVIEW_PAGES_DIR = GENERATED_DIR / "review-pages"

PAGE_LAYOUT_DECORATIVE = "decorative/structural"
PAGE_LAYOUT_TOC = "toc"
PAGE_LAYOUT_TABLE = "table/form"
PAGE_LAYOUT_LIST = "list"
PAGE_LAYOUT_PROSE = "prose"

STRUCTURAL_HEADING_RE = re.compile(r"^제\s*[\d-]+\s*(?:편|장|절)\b")
SMALL_FONT_STRUCTURAL_HEADER_RE = re.compile(r"^제\s*\d+(?:-\d+)?\s*(?:편|장|절)\b")
ARTICLE_LINE_RE = re.compile(r"^제\s*\d+(?:의\d+)?조(?:의\d+)?\(")
DATE_RE = re.compile(r"^\d{4}년\s+\d{1,2}월\s+\d{1,2}일$")
RUNNING_HEADER_PATTERNS = (
    re.compile(r"^2024\s+심판편람\s+제14판$"),
    re.compile(r"^심판편람\(제14판\)$"),
    re.compile(r"^Intellectual\s+Property\s+Trial\s+and$", re.IGNORECASE),
    re.compile(r"^Appeal\s+Board$", re.IGNORECASE),
    re.compile(r"^제\s+\d+\s+편$"),
    re.compile(r"^목$"),
    re.compile(r"^차$"),
)
FRAGMENT_HEADER_RE = re.compile(r"^(?:제|편|\d+|목|차)$")
LEADER_DOTS_RE = re.compile(r"(?:[·.]\s*){5,}")
LINE_END_PAGE_NUMBER_RE = re.compile(r"(?:\b\d{1,4}\b|[ivxlcdm]{1,12})\)?$", re.IGNORECASE)
ROUND_BULLET_RE = re.compile(r"^[oO](?:\s+|$)")
LIST_MARKER_RE = re.compile(
    r"^(?:"
    r"\d+[.)]"
    r"|[가-힣][.)]"
    r"|[(（]\d+[)）]"
    r"|[(（][가-힣IVXLC]{1,3}[)）]"
    r"|[①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮]"
    r"|[⑴⑵⑶⑷⑸⑹⑺⑻⑼⑽]"
    r"|[※•◦▪■□▶☞◆◇○●∘]"
    r"|[A-Za-z][.)]"
    r"|[oO]"
    r")(?:\s+|$)"
)
SENTENCE_END_RE = re.compile(r"[.!?…:]$")
BOUNDARY_REASONS = {
    "page-start",
    "gap",
    "indent",
    "style-change",
    "list-marker",
    "toc-entry",
    "table-row",
    "override",
    "page-merge",
}


def load_paragraph_overrides() -> dict[int, dict[str, Any]]:
    if not OVERRIDES_PATH.exists():
        return {}

    payload = json.loads(OVERRIDES_PATH.read_text(encoding="utf-8"))
    pages = payload.get("pages", [])
    return {int(page["pageNumber"]): page for page in pages if page.get("pageNumber") is not None}


def _is_centered_bbox(bbox: tuple[float, float, float, float], page_width: float) -> bool:
    left, _, right, _ = bbox
    width = right - left
    center = (left + right) / 2
    left_margin = left
    right_margin = page_width - right
    return (
        abs(center - (page_width / 2)) <= page_width * 0.1
        and abs(left_margin - right_margin) <= page_width * 0.12
        and width <= page_width * 0.6
    )


def _classify_line_kind(line: dict[str, Any], page_width: float, page_height: float) -> str:
    text = line["text"]
    if DATE_RE.match(text):
        return "date"
    if "원장" in text and (line["isCentered"] or (len(text) <= 24 and float(line["top"]) >= page_height * 0.8)):
        return "signature"
    if line["isCentered"] and (len(text) <= 20 or STRUCTURAL_HEADING_RE.match(text)):
        return "heading"
    if STRUCTURAL_HEADING_RE.match(text) and line["fontSize"] >= 11.5:
        return "heading"
    return "body"


def _dominant_float(values: list[float], default: float) -> float:
    if not values:
        return default
    counter = Counter(round(float(value), 1) for value in values)
    return float(counter.most_common(1)[0][0])


def _dominant_int(values: list[int], default: int = 0) -> int:
    if not values:
        return default
    counter = Counter(int(value) for value in values)
    return int(counter.most_common(1)[0][0])


def _cluster_positions(values: list[float], *, tolerance: float) -> list[float]:
    if not values:
        return []
    ordered = sorted(float(value) for value in values)
    clusters: list[list[float]] = [[ordered[0]]]
    for value in ordered[1:]:
        if abs(value - clusters[-1][-1]) <= tolerance:
            clusters[-1].append(value)
        else:
            clusters.append([value])
    return [float(median(cluster)) for cluster in clusters]


def _has_leader_dots(text: str) -> bool:
    return LEADER_DOTS_RE.search(text) is not None


def _ends_with_page_number(text: str) -> bool:
    cleaned = normalize_line(text).rstrip(")")
    if not cleaned:
        return False
    last_token = cleaned.split()[-1]
    if _has_leader_dots(cleaned):
        return bool(LINE_END_PAGE_NUMBER_RE.search(last_token))
    return bool(re.fullmatch(r"(?:\d{1,4}|[ivxlcdm]{1,12})", last_token, re.IGNORECASE))


def _is_list_marker_line(text: str) -> bool:
    stripped = normalize_line(text)
    return bool(
        LIST_MARKER_RE.match(stripped)
        or ARTICLE_LINE_RE.match(stripped)
        or stripped.startswith("§")
        or _has_leader_dots(stripped)
    )


def _is_round_bullet_line(text: str) -> bool:
    return ROUND_BULLET_RE.match(normalize_line(text)) is not None


def _is_small_running_structural_header(*, text: str, top: float, font_size: float) -> bool:
    return top < 110.0 and font_size <= 9.5 and SMALL_FONT_STRUCTURAL_HEADER_RE.match(text) is not None


def _line_font_delta(line: dict[str, Any], dominant_body_font: float | None) -> float:
    if dominant_body_font is None:
        return 0.0
    return abs(float(line["fontSize"]) - float(dominant_body_font))


def extract_page_lines(page: pymupdf.Page) -> list[dict[str, Any]]:
    page_width = float(page.rect.width)
    page_height = float(page.rect.height)
    records: list[dict[str, Any]] = []
    next_legacy_block_index = 0

    for block_index, block in enumerate(extract_page_blocks(page)):
        if block.get("type") != 0:
            continue

        block_lines: list[dict[str, Any]] = []
        for line_index, line in enumerate(block.get("lines", [])):
            raw_text = "".join(str(span.get("text", "")) for span in line.get("spans", []))
            text = normalize_line(raw_text)
            if not text:
                continue

            bbox = tuple(float(value) for value in line.get("bbox", block.get("bbox")))
            left, top, right, bottom = bbox
            if parse_page_label_line(text):
                continue
            if top < 140 and any(pattern.match(text) for pattern in RUNNING_HEADER_PATTERNS):
                continue
            if top < 140 and FRAGMENT_HEADER_RE.match(text):
                continue

            span_texts = [normalize_line(str(span.get("text", ""))) for span in line.get("spans", [])]
            non_empty_spans = [span for span in line.get("spans", []) if normalize_line(str(span.get("text", "")))]
            font_sizes = [float(span.get("size", 0.0)) for span in non_empty_spans]
            font_flags = [int(span.get("flags", 0)) for span in non_empty_spans]
            line_record = {
                "index": -1,
                "blockIndex": int(block_index),
                "legacyBlockIndex": int(next_legacy_block_index),
                "lineIndex": int(line_index),
                "text": text,
                "bbox": bbox,
                "left": left,
                "top": top,
                "right": right,
                "bottom": bottom,
                "width": right - left,
                "spanCount": len(non_empty_spans),
                "fontSize": _dominant_float(font_sizes, 0.0),
                "fontFlags": _dominant_int(font_flags, 0),
                "isCentered": _is_centered_bbox(bbox, page_width),
                "sourceSpanTexts": [value for value in span_texts if value],
            }
            if _is_small_running_structural_header(
                text=text,
                top=float(top),
                font_size=float(line_record["fontSize"]),
            ):
                continue
            block_lines.append(line_record)

        if not block_lines:
            continue

        records.extend(block_lines)
        next_legacy_block_index += 1

    records.sort(key=lambda item: (float(item["top"]), float(item["left"]), int(item["blockIndex"]), int(item["lineIndex"])))
    records = _prune_top_structural_duplicates(records)

    for index, record in enumerate(records):
        record["index"] = index
        record["kind"] = _classify_line_kind(record, page_width, page_height)

    return records


def _prune_top_structural_duplicates(lines: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for index, line in enumerate(lines):
        text = str(line["text"])
        if (
            index < 6
            and STRUCTURAL_HEADING_RE.match(text)
            and any(text == str(lines[next_index]["text"]) for next_index in range(index + 1, min(len(lines), index + 4)))
        ):
            continue
        result.append(line)
    return result


def _build_source_blocks(lines: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_legacy_block: dict[int, list[dict[str, Any]]] = defaultdict(list)
    order: list[int] = []
    for line in lines:
        legacy_block_index = int(line["legacyBlockIndex"])
        if legacy_block_index not in by_legacy_block:
            order.append(legacy_block_index)
        by_legacy_block[legacy_block_index].append(line)

    blocks: list[dict[str, Any]] = []
    for index, legacy_block_index in enumerate(order):
        block_lines = by_legacy_block[legacy_block_index]
        left = min(float(line["left"]) for line in block_lines)
        top = min(float(line["top"]) for line in block_lines)
        right = max(float(line["right"]) for line in block_lines)
        bottom = max(float(line["bottom"]) for line in block_lines)
        blocks.append(
            {
                "index": index,
                "legacyBlockIndex": legacy_block_index,
                "blockIndex": int(block_lines[0]["blockIndex"]),
                "text": " ".join(str(line["text"]) for line in block_lines).strip(),
                "bbox": [round(left, 1), round(top, 1), round(right, 1), round(bottom, 1)],
                "kind": str(block_lines[0]["kind"]),
                "centered": bool(all(bool(line["isCentered"]) for line in block_lines)),
                "sourceLines": [int(line["index"]) for line in block_lines],
            }
        )
    return blocks


def _determine_dominant_body_font(lines: list[dict[str, Any]]) -> float | None:
    candidates = [
        float(line["fontSize"])
        for line in lines
        if not line["isCentered"]
        and len(str(line["text"])) >= 8
        and line["kind"] not in {"date", "signature"}
        and not _has_leader_dots(str(line["text"]))
    ]
    if not candidates:
        return None
    return _dominant_float(candidates, 0.0)


def _matches_dominant_body_font(line: dict[str, Any], dominant_body_font: float | None) -> bool:
    if dominant_body_font is None:
        return False
    return abs(float(line["fontSize"]) - float(dominant_body_font)) <= 0.8


def _body_like_line(line: dict[str, Any], page_width: float, dominant_body_font: float | None) -> bool:
    return (
        _matches_dominant_body_font(line, dominant_body_font)
        and not line["isCentered"]
        and line["kind"] == "body"
        and float(line["width"]) >= page_width * 0.45
        and not _has_leader_dots(str(line["text"]))
    )


def _compute_body_left_anchor(lines: list[dict[str, Any]], page_width: float, dominant_body_font: float | None) -> float:
    candidates = [float(line["left"]) for line in lines if _body_like_line(line, page_width, dominant_body_font)]
    if not candidates:
        return 0.0
    return float(median(candidates))


def _compute_base_line_gap(lines: list[dict[str, Any]], page_width: float, dominant_body_font: float | None) -> float:
    gaps: list[float] = []
    for left, right in zip(lines, lines[1:]):
        if not _body_like_line(left, page_width, dominant_body_font):
            continue
        if not _body_like_line(right, page_width, dominant_body_font):
            continue
        if abs(float(right["left"]) - float(left["left"])) > 6.0:
            continue
        gap = float(right["top"]) - float(left["bottom"])
        if gap > 0:
            gaps.append(gap)
    if not gaps:
        return 10.0
    return float(median(gaps))


def _longest_body_run(lines: list[dict[str, Any]], page_width: float, dominant_body_font: float | None) -> int:
    longest = 0
    current = 0
    for line in lines:
        if _body_like_line(line, page_width, dominant_body_font):
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return longest


def _build_row_bands(lines: list[dict[str, Any]], *, tolerance: float = 3.0) -> list[dict[str, Any]]:
    bands: list[dict[str, Any]] = []
    for line in lines:
        if bands and float(line["top"]) <= float(bands[-1]["bottom"]) + tolerance:
            bands[-1]["lines"].append(line)
            bands[-1]["bottom"] = max(float(bands[-1]["bottom"]), float(line["bottom"]))
        else:
            bands.append({"top": float(line["top"]), "bottom": float(line["bottom"]), "lines": [line]})
    return bands


def _count_table_bands(lines: list[dict[str, Any]], page_width: float) -> int:
    bands = _build_row_bands(lines)
    multi_column_rows = 0
    for band in bands:
        short_lines = [line for line in band["lines"] if float(line["width"]) <= page_width * 0.35]
        clusters = _cluster_positions([float(line["left"]) for line in short_lines], tolerance=18.0)
        if len(clusters) >= 3:
            multi_column_rows += 1
    return multi_column_rows


def _has_repeated_short_anchor_grid(lines: list[dict[str, Any]], page_width: float) -> bool:
    short_lines = [line for line in lines if float(line["width"]) <= page_width * 0.35]
    if len(short_lines) < 15:
        return False
    anchor_clusters = _cluster_positions([float(line["left"]) for line in short_lines], tolerance=18.0)
    if len(anchor_clusters) < 3:
        return False
    counts: list[int] = []
    for anchor in anchor_clusters:
        counts.append(sum(1 for line in short_lines if abs(float(line["left"]) - anchor) <= 18.0))
    return sum(1 for count in counts if count >= 5) >= 3


def _classify_page_layout(lines: list[dict[str, Any]], page_width: float, dominant_body_font: float | None) -> str:
    if not lines:
        return PAGE_LAYOUT_DECORATIVE

    line_count = len(lines)
    centered_ratio = sum(1 for line in lines if line["isCentered"]) / float(line_count)
    body_run = _longest_body_run(lines, page_width, dominant_body_font)
    leader_ratio = sum(1 for line in lines if _has_leader_dots(str(line["text"]))) / float(line_count)
    page_number_ratio = sum(1 for line in lines if _ends_with_page_number(str(line["text"]))) / float(line_count)
    table_bands = _count_table_bands(lines, page_width)
    list_marker_count = sum(1 for line in lines if _is_list_marker_line(str(line["text"])))
    list_marker_ratio = list_marker_count / float(line_count)
    round_bullet_count = sum(1 for line in lines if _is_round_bullet_line(str(line["text"])))

    if line_count <= 8 and (centered_ratio >= 0.5 or body_run < 3):
        return PAGE_LAYOUT_DECORATIVE
    if leader_ratio >= 0.45 and page_number_ratio >= 0.35:
        return PAGE_LAYOUT_TOC
    if table_bands >= 5 or _has_repeated_short_anchor_grid(lines, page_width):
        return PAGE_LAYOUT_TABLE
    if round_bullet_count >= 1 and line_count >= 12:
        return PAGE_LAYOUT_LIST
    if (list_marker_count >= 3 and (list_marker_ratio >= 0.3 or body_run < 3)) or leader_ratio >= 0.25:
        return PAGE_LAYOUT_LIST
    return PAGE_LAYOUT_PROSE


def _coerce_boundary_reason(reason: str) -> str:
    return reason if reason in BOUNDARY_REASONS else "style-change"


def _build_prose_groups(lines: list[dict[str, Any]], *, page_width: float, dominant_body_font: float | None) -> list[dict[str, Any]]:
    if not lines:
        return []

    body_left_anchor = _compute_body_left_anchor(lines, page_width, dominant_body_font)
    base_gap = _compute_base_line_gap(lines, page_width, dominant_body_font)
    paragraph_gap = max(base_gap + 3.5, base_gap * 1.4)

    groups: list[dict[str, Any]] = []
    current_lines: list[int] = []
    current_reason = "page-start"

    for line in lines:
        if not current_lines:
            current_lines = [int(line["index"])]
            current_reason = "page-start"
            continue

        previous = lines[current_lines[-1]]
        gap = float(line["top"]) - float(previous["bottom"])
        starts_indented = float(line["left"]) >= body_left_anchor + 12.0
        starts_at_anchor = abs(float(line["left"]) - body_left_anchor) <= 6.0
        previous_ends_sentence = bool(SENTENCE_END_RE.search(str(previous["text"]).rstrip()))
        style_changed = (
            previous["kind"] != line["kind"]
            or bool(previous["isCentered"]) != bool(line["isCentered"])
            or _line_font_delta(line, dominant_body_font) > 0.8
            or _line_font_delta(previous, dominant_body_font) > 0.8
        )

        reason: str | None = None
        if _is_list_marker_line(str(line["text"])):
            reason = "list-marker"
        elif style_changed:
            reason = "style-change"
        elif gap >= paragraph_gap:
            reason = "gap"
        elif starts_indented:
            reason = "indent"
        elif previous_ends_sentence and starts_at_anchor and gap > base_gap + 1.0:
            reason = "gap"

        if reason is not None:
            groups.append({"lineIndices": current_lines, "boundaryReason": _coerce_boundary_reason(current_reason)})
            current_lines = [int(line["index"])]
            current_reason = reason
        else:
            current_lines.append(int(line["index"]))

    if current_lines:
        groups.append({"lineIndices": current_lines, "boundaryReason": _coerce_boundary_reason(current_reason)})

    return _split_oversized_prose_groups(groups, lines, body_left_anchor=body_left_anchor)


def _split_oversized_prose_groups(
    groups: list[dict[str, Any]],
    lines: list[dict[str, Any]],
    *,
    body_left_anchor: float,
    max_chars: int = 900,
) -> list[dict[str, Any]]:
    line_map = {int(line["index"]): line for line in lines}
    result: list[dict[str, Any]] = []

    for group in groups:
        pending: list[dict[str, Any]] = [group]
        while pending:
            current = pending.pop(0)
            line_indices = [int(index) for index in current["lineIndices"]]
            text = " ".join(str(line_map[index]["text"]) for index in line_indices if index in line_map).strip()
            if len(text) <= max_chars or len(line_indices) < 2:
                result.append(current)
                continue

            candidate_breaks: list[tuple[int, str, int]] = []
            rendered_length = 0
            for offset, (left_index, right_index) in enumerate(zip(line_indices, line_indices[1:]), start=1):
                left_line = line_map[left_index]
                right_line = line_map[right_index]
                rendered_length += len(str(left_line["text"])) + 1
                right_starts_at_anchor = abs(float(right_line["left"]) - body_left_anchor) <= 6.0
                if _is_list_marker_line(str(right_line["text"])) and rendered_length >= 160:
                    candidate_breaks.append((offset, "list-marker", rendered_length))
                    continue
                if SENTENCE_END_RE.search(str(left_line["text"]).rstrip()) and right_starts_at_anchor:
                    candidate_breaks.append((offset, "gap", rendered_length))

            preferred = [candidate for candidate in candidate_breaks if 180 <= candidate[2] <= max_chars]
            selected = preferred[-1] if preferred else (candidate_breaks[0] if candidate_breaks else None)
            if selected is None:
                result.append(current)
                continue

            split_offset, boundary_reason, _ = selected
            pending.insert(
                0,
                {
                    "lineIndices": line_indices[split_offset:],
                    "boundaryReason": boundary_reason,
                },
            )
            pending.insert(
                0,
                {
                    "lineIndices": line_indices[:split_offset],
                    "boundaryReason": current["boundaryReason"],
                },
            )

    return result


def _build_toc_groups(lines: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: list[dict[str, Any]] = []
    current_lines: list[int] = []
    current_reason = "page-start"
    current_left = 0.0

    for line in lines:
        starts_entry = _has_leader_dots(str(line["text"])) or _ends_with_page_number(str(line["text"]))
        continuation = current_lines and float(line["left"]) > current_left + 8.0 and not _ends_with_page_number(str(line["text"]))

        if not current_lines:
            current_lines = [int(line["index"])]
            current_reason = "page-start"
            current_left = float(line["left"])
            continue

        if starts_entry and not continuation:
            groups.append({"lineIndices": current_lines, "boundaryReason": _coerce_boundary_reason(current_reason)})
            current_lines = [int(line["index"])]
            current_reason = "toc-entry"
            current_left = float(line["left"])
        else:
            current_lines.append(int(line["index"]))

    if current_lines:
        groups.append({"lineIndices": current_lines, "boundaryReason": _coerce_boundary_reason(current_reason)})

    return groups


def _build_list_groups(lines: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: list[dict[str, Any]] = []
    current_lines: list[int] = []
    current_reason = "page-start"
    current_left = 0.0

    for line in lines:
        starts_entry = _is_list_marker_line(str(line["text"]))
        continuation = current_lines and not starts_entry and float(line["left"]) >= current_left - 2.0

        if not current_lines:
            current_lines = [int(line["index"])]
            current_reason = "page-start"
            current_left = float(line["left"])
            continue

        if starts_entry and not continuation:
            groups.append({"lineIndices": current_lines, "boundaryReason": _coerce_boundary_reason(current_reason)})
            current_lines = [int(line["index"])]
            current_reason = "list-marker"
            current_left = float(line["left"])
        else:
            current_lines.append(int(line["index"]))

    if current_lines:
        groups.append({"lineIndices": current_lines, "boundaryReason": _coerce_boundary_reason(current_reason)})

    return groups


def _build_table_groups(lines: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: list[dict[str, Any]] = []
    for index, band in enumerate(_build_row_bands(lines)):
        line_indices = [int(line["index"]) for line in sorted(band["lines"], key=lambda item: (float(item["left"]), float(item["top"])))]
        groups.append({"lineIndices": line_indices, "boundaryReason": "page-start" if index == 0 else "table-row"})
    return groups


def _build_decorative_groups(lines: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: list[dict[str, Any]] = []
    for index, line in enumerate(lines):
        groups.append({"lineIndices": [int(line["index"])], "boundaryReason": "page-start" if index == 0 else "style-change"})
    return groups


def _build_auto_groups(
    lines: list[dict[str, Any]],
    *,
    page_width: float,
    page_layout_kind: str,
    dominant_body_font: float | None,
) -> list[dict[str, Any]]:
    if page_layout_kind == PAGE_LAYOUT_PROSE:
        return _build_prose_groups(lines, page_width=page_width, dominant_body_font=dominant_body_font)
    if page_layout_kind == PAGE_LAYOUT_TOC:
        return _build_toc_groups(lines)
    if page_layout_kind == PAGE_LAYOUT_LIST:
        return _build_list_groups(lines)
    if page_layout_kind == PAGE_LAYOUT_TABLE:
        return _build_table_groups(lines)
    return _build_decorative_groups(lines)


def _expand_override_groups(
    lines: list[dict[str, Any]],
    override: dict[str, Any],
) -> tuple[list[list[int]], list[list[int]]]:
    line_index_set = {int(line["index"]) for line in lines}
    legacy_block_map: dict[int, list[int]] = defaultdict(list)
    for line in lines:
        legacy_block_map[int(line["legacyBlockIndex"])].append(int(line["index"]))

    custom_groups: list[list[int]] = []
    if override.get("lineGroups"):
        custom_groups.extend(
            [
                [int(index) for index in group if int(index) in line_index_set]
                for group in override.get("lineGroups", [])
                if group
            ]
        )
        force_standalone = [
            [int(index) for index in legacy_group if int(index) in line_index_set]
            for legacy_group in ([index] for index in override.get("forceStandalone", []))
        ]
    else:
        for group in override.get("groups", []):
            expanded: list[int] = []
            for block_index in group:
                expanded.extend(legacy_block_map.get(int(block_index), []))
            if expanded:
                custom_groups.append(expanded)
        force_standalone = [
            list(legacy_block_map.get(int(block_index), []))
            for block_index in override.get("forceStandalone", [])
            if legacy_block_map.get(int(block_index))
        ]

    return (
        [group for group in custom_groups if group],
        [group for group in force_standalone if group],
    )


def _apply_override_groups(
    groups: list[dict[str, Any]],
    lines: list[dict[str, Any]],
    override: dict[str, Any],
) -> list[dict[str, Any]]:
    custom_groups, force_standalone_groups = _expand_override_groups(lines, override)
    if not custom_groups and not force_standalone_groups:
        return groups

    custom_for_index: dict[int, tuple[int, ...]] = {}
    for group in custom_groups:
        frozen = tuple(group)
        for index in group:
            custom_for_index[int(index)] = frozen

    merged: list[dict[str, Any]] = []
    emitted_custom: set[tuple[int, ...]] = set()
    for group in groups:
        current: list[int] = []
        for index in group["lineIndices"]:
            custom = custom_for_index.get(int(index))
            if custom:
                if current:
                    merged.append({"lineIndices": current, "boundaryReason": group["boundaryReason"]})
                    current = []
                if custom not in emitted_custom:
                    merged.append({"lineIndices": list(custom), "boundaryReason": "override"})
                    emitted_custom.add(custom)
                continue
            current.append(int(index))
        if current:
            merged.append({"lineIndices": current, "boundaryReason": group["boundaryReason"]})

    if not force_standalone_groups:
        return merged

    force_lookup = {tuple(group): set(group) for group in force_standalone_groups}
    final: list[dict[str, Any]] = []
    for group in merged:
        current: list[int] = []
        for index in group["lineIndices"]:
            standalone = next((key for key, value in force_lookup.items() if int(index) in value), None)
            if standalone:
                if current:
                    final.append({"lineIndices": current, "boundaryReason": group["boundaryReason"]})
                    current = []
                if not any(existing["lineIndices"] == list(standalone) for existing in final):
                    final.append({"lineIndices": list(standalone), "boundaryReason": "override"})
            else:
                current.append(int(index))
        if current:
            final.append({"lineIndices": current, "boundaryReason": group["boundaryReason"]})

    return final


def _is_incomplete_paragraph(text: str) -> bool:
    normalized = normalize_bookmark_title(text)
    if not normalized:
        return False
    return SENTENCE_END_RE.search(normalized.rstrip()) is None


def _paragraph_kind(
    first_line: dict[str, Any],
    *,
    page_layout_kind: str,
    dominant_body_font: float | None,
) -> str:
    if page_layout_kind != PAGE_LAYOUT_PROSE:
        if first_line["kind"] in {"heading", "date", "signature"}:
            return str(first_line["kind"])
        return page_layout_kind
    if first_line["kind"] in {"heading", "date", "signature"}:
        return str(first_line["kind"])
    if ARTICLE_LINE_RE.match(str(first_line["text"])):
        return "heading"
    if _is_list_marker_line(str(first_line["text"])) and _line_font_delta(first_line, dominant_body_font) > 0.8:
        return "heading"
    return "body"


def _render_group_text(
    group_lines: list[dict[str, Any]],
    *,
    page_layout_kind: str,
) -> str:
    if page_layout_kind == PAGE_LAYOUT_TABLE:
        return " | ".join(str(line["text"]) for line in sorted(group_lines, key=lambda item: (float(item["left"]), float(item["top"])))).strip()
    return " ".join(str(line["text"]) for line in group_lines).strip()


def _page_confidence(
    *,
    page_layout_kind: str,
    dominant_body_font: float | None,
    has_override: bool,
    paragraph_count: int,
) -> str:
    if has_override or paragraph_count == 0:
        return "low"
    if dominant_body_font is None:
        return "medium"
    if page_layout_kind in {PAGE_LAYOUT_TOC, PAGE_LAYOUT_LIST, PAGE_LAYOUT_TABLE, PAGE_LAYOUT_DECORATIVE}:
        return "medium"
    return "high"


def build_page_review_entry(
    page: pymupdf.Page,
    page_meta: dict[str, Any],
    *,
    override: dict[str, Any] | None = None,
    previous_page_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    page_width = float(page.rect.width)
    lines = extract_page_lines(page)
    source_blocks = _build_source_blocks(lines)
    dominant_body_font = _determine_dominant_body_font(lines)
    base_line_gap = _compute_base_line_gap(lines, page_width, dominant_body_font)
    body_left_anchor = _compute_body_left_anchor(lines, page_width, dominant_body_font)
    page_layout_kind = _classify_page_layout(lines, page_width, dominant_body_font)
    groups = _build_auto_groups(
        lines,
        page_width=page_width,
        page_layout_kind=page_layout_kind,
        dominant_body_font=dominant_body_font,
    )
    if override:
        groups = _apply_override_groups(groups, lines, override)

    line_map = {int(line["index"]): line for line in lines}
    legacy_block_to_grouped_index = {int(block["legacyBlockIndex"]): int(block["index"]) for block in source_blocks}

    paragraphs: list[dict[str, Any]] = []
    for group_index, group in enumerate(groups):
        group_lines = [line_map[index] for index in group["lineIndices"] if index in line_map]
        if not group_lines:
            continue

        paragraph_source_blocks = sorted(
            {
                legacy_block_to_grouped_index[int(line["legacyBlockIndex"])]
                for line in group_lines
                if int(line["legacyBlockIndex"]) in legacy_block_to_grouped_index
            }
        )
        first_line = group_lines[0]
        paragraphs.append(
            {
                "index": group_index,
                "text": _render_group_text(group_lines, page_layout_kind=page_layout_kind),
                "sourceBlocks": paragraph_source_blocks,
                "sourceLines": [int(line["index"]) for line in group_lines],
                "kind": _paragraph_kind(first_line, page_layout_kind=page_layout_kind, dominant_body_font=dominant_body_font),
                "boundaryReason": _coerce_boundary_reason(str(group["boundaryReason"])),
            }
        )

    merge_first_group = False
    if override and "mergeFirstGroupWithPreviousPage" in override:
        merge_first_group = bool(override["mergeFirstGroupWithPreviousPage"])
        if merge_first_group and paragraphs:
            paragraphs[0]["boundaryReason"] = "page-merge"
    elif previous_page_context and paragraphs and page_layout_kind == PAGE_LAYOUT_PROSE:
        previous_layout_kind = str(previous_page_context.get("pageLayoutKind") or "")
        previous_last_paragraph = str(previous_page_context.get("lastParagraphText") or "")
        first_paragraph = paragraphs[0]
        first_line = line_map[first_paragraph["sourceLines"][0]]
        merge_first_group = (
            previous_layout_kind == PAGE_LAYOUT_PROSE
            and first_paragraph["kind"] == "body"
            and _is_incomplete_paragraph(previous_last_paragraph)
            and dominant_body_font is not None
            and abs(float(first_line["fontSize"]) - float(dominant_body_font)) <= 0.8
            and abs(float(body_left_anchor) - float(previous_page_context.get("bodyLeftAnchor") or 0.0)) <= 6.0
            and len(previous_last_paragraph) + len(first_paragraph["text"]) <= 900
        )
        if merge_first_group:
            paragraphs[0]["boundaryReason"] = "page-merge"

    return {
        "pageNumber": int(page.number + 1),
        "pageLabel": page_meta.get("pageLabel"),
        "pageLayoutKind": page_layout_kind,
        "confidence": _page_confidence(
            page_layout_kind=page_layout_kind,
            dominant_body_font=dominant_body_font,
            has_override=bool(override),
            paragraph_count=len(paragraphs),
        ),
        "sourceBlocks": source_blocks,
        "sourceLines": [
            {
                "index": int(line["index"]),
                "blockIndex": int(line["blockIndex"]),
                "legacyBlockIndex": int(line["legacyBlockIndex"]),
                "lineIndex": int(line["lineIndex"]),
                "text": str(line["text"]),
                "bbox": [round(float(value), 1) for value in line["bbox"]],
                "kind": str(line["kind"]),
                "centered": bool(line["isCentered"]),
                "fontSize": round(float(line["fontSize"]), 1),
                "fontFlags": int(line["fontFlags"]),
                "spanCount": int(line["spanCount"]),
                "sourceSpanTexts": [str(value) for value in line["sourceSpanTexts"]],
            }
            for line in lines
        ],
        "paragraphs": paragraphs,
        "paragraphCount": len(paragraphs),
        "hasOverride": bool(override),
        "mergeFirstGroupWithPreviousPage": merge_first_group,
        "dominantBodyFont": None if dominant_body_font is None else round(float(dominant_body_font), 1),
        "bodyLeftAnchor": round(float(body_left_anchor), 1),
        "baseLineGap": round(float(base_line_gap), 1),
    }


def build_page_review_entries(document: pymupdf.Document, inventory: dict[str, Any]) -> list[dict[str, Any]]:
    overrides = load_paragraph_overrides()
    page_meta_map = {int(page["pageNumber"]): page for page in inventory.get("pages", [])}
    entries: list[dict[str, Any]] = []
    previous_page_context: dict[str, Any] | None = None

    for page_number in range(1, document.page_count + 1):
        page = document.load_page(page_number - 1)
        page_meta = page_meta_map.get(page_number, {"pageNumber": page_number, "pageLabel": None})
        override = overrides.get(page_number)
        entry = build_page_review_entry(
            page,
            page_meta,
            override=override,
            previous_page_context=previous_page_context,
        )
        entries.append(entry)

        previous_page_context = {
            "pageLayoutKind": entry["pageLayoutKind"],
            "bodyLeftAnchor": entry["bodyLeftAnchor"],
            "lastParagraphText": entry["paragraphs"][-1]["text"] if entry["paragraphs"] else "",
        }

    return entries


def prepare_review_pages_dir() -> Path:
    if REVIEW_PAGES_DIR.exists():
        shutil.rmtree(REVIEW_PAGES_DIR)
    REVIEW_PAGES_DIR.mkdir(parents=True, exist_ok=True)
    return REVIEW_PAGES_DIR


def render_review_page_image(page: pymupdf.Page, target: Path, *, width_px: int = 900, quality: int = 75) -> None:
    scale = width_px / float(page.rect.width)
    pixmap = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False)
    target.write_bytes(pixmap.tobytes("jpg", jpg_quality=quality))
