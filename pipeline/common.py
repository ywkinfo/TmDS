from __future__ import annotations

import json
import re
from html import escape
from pathlib import Path
from typing import Any

import pymupdf


ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
SOURCE_DIR = DATA_DIR / "source"
GENERATED_DIR = DATA_DIR / "generated"
CONFIG_PATH = SOURCE_DIR / "source-config.json"

HYPHEN_LABEL_RE = re.compile(r"^-\s*([ivxlcdm]+|\d{1,4})\s*-$", re.IGNORECASE)
WHITESPACE_RE = re.compile(r"\s+")
SLUG_SANITIZE_RE = re.compile(r"[^0-9A-Za-z가-힣-]+")
STRUCTURAL_HEADING_RE = re.compile(r"^제\s*[\d-]+\s*(?:편|장|절)\b")
BROKEN_TEXT_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"산업재\s+산권"), "산업재산권"),
    (re.compile(r"특별행정\s+심판"), "특별행정심판"),
    (re.compile(r"행정\s+심판"), "행정심판"),
    (re.compile(r"국선대리\s+인"), "국선대리인"),
    (re.compile(r"법정대리\s+인"), "법정대리인"),
    (re.compile(r"소송대리\s+인"), "소송대리인"),
    (re.compile(r"특허관리\s+인"), "특허관리인"),
    (re.compile(r"무효처\s+분"), "무효처분"),
    (re.compile(r"특\s+허"), "특허"),
    (re.compile(r"심\s+판"), "심판"),
    (re.compile(r"청\s+구"), "청구"),
    (re.compile(r"처\s+분"), "처분"),
    (re.compile(r"또\s+는"), "또는"),
    (re.compile(r"의\s+하여"), "의하여"),
    (re.compile(r"말\s+한다"), "말한다"),
    (re.compile(r"대\s+리인"), "대리인"),
    (re.compile(r"대리\s+인"), "대리인"),
    (re.compile(r"심판\s+원장"), "심판원장"),
    (re.compile(r"심판\s+원"), "심판원"),
    (re.compile(r"심판\s+관"), "심판관"),
    (re.compile(r"심판\s+기관"), "심판기관"),
    (re.compile(r"심판\s+절차"), "심판절차"),
    (re.compile(r"심판\s+청구"), "심판청구"),
    (re.compile(r"심판\s+합의체"), "심판합의체"),
    (re.compile(r"특허\s+심판"), "특허심판"),
    (re.compile(r"청구\s+인"), "청구인"),
    (re.compile(r"피\s+청구인"), "피청구인"),
    (re.compile(r"특허\s+법"), "특허법"),
    (re.compile(r"상표\s+법"), "상표법"),
    (re.compile(r"실용신안\s+법"), "실용신안법"),
    (re.compile(r"민사소송\s+법"), "민사소송법"),
    (re.compile(r"행정소송\s+법"), "행정소송법"),
    (re.compile(r"이\s+에(?=\s+(?:대한|대해|따른|관한|의한|따라))"), "이에"),
)
RUNNING_HEADER_PATTERNS = (
    re.compile(r"^2024\s+심판편람\s+제14판$"),
    re.compile(r"^Intellectual\s+Property\s+Trial\s+and$", re.IGNORECASE),
    re.compile(r"^Appeal\s+Board$", re.IGNORECASE),
    re.compile(r"^제\s+\d+\s+편$"),
    re.compile(r"^부\s*록$"),
)


def fail(message: str) -> None:
    raise SystemExit(message)


def load_config() -> dict[str, Any]:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def resolve_pdf_path(config: dict[str, Any]) -> Path:
    pdf_path = ROOT_DIR / str(config["sourcePdf"])
    if not pdf_path.exists():
        fail(f"원본 PDF를 찾을 수 없습니다: {pdf_path}")
    return pdf_path


def open_pdf(config: dict[str, Any]) -> pymupdf.Document:
    return pymupdf.open(str(resolve_pdf_path(config)))


def ensure_generated_dir() -> Path:
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    return GENERATED_DIR


def write_json(filename: str, data: Any) -> Path:
    ensure_generated_dir()
    target = GENERATED_DIR / filename
    target.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target


def load_generated_json(filename: str) -> Any:
    target = GENERATED_DIR / filename
    if not target.exists():
        fail(f"generated 파일이 없습니다: {target}")
    return json.loads(target.read_text(encoding="utf-8"))


def print_json_summary(label: str, payload: dict[str, Any]) -> None:
    print(json.dumps({"label": label, **payload}, ensure_ascii=False))


def normalize_line(value: str) -> str:
    return WHITESPACE_RE.sub(" ", str(value).replace("\x00", " ")).strip()


def repair_extracted_text_spacing(value: str) -> str:
    repaired = normalize_line(value)
    previous = None
    while repaired and repaired != previous:
        previous = repaired
        for pattern, replacement in BROKEN_TEXT_PATTERNS:
            repaired = pattern.sub(replacement, repaired)
        repaired = normalize_line(repaired)
    return repaired


def merge_extracted_text_segments(*segments: str) -> str:
    parts = [normalize_line(segment) for segment in segments if normalize_line(segment)]
    if not parts:
        return ""
    return repair_extracted_text_spacing(" ".join(parts))


def normalize_space(value: str | None) -> str:
    return normalize_line(value or "")


def normalize_search_text(value: str | None) -> str:
    return repair_extracted_text_spacing(normalize_space(value))


def clean_title(value: str | None) -> str:
    normalized = (
        normalize_space(value)
        .replace("․", " ")
        .replace("ㆍ", " ")
        .replace("·", " ")
    )
    return normalize_space(normalized)


def normalize_bookmark_title(value: str | None) -> str:
    return clean_title(value).replace(" ,", ",")


def slugify(value: str | None, *, max_length: int = 80) -> str:
    text = normalize_bookmark_title(value)
    text = text.replace("/", "-").replace("(", "").replace(")", "")
    text = SLUG_SANITIZE_RE.sub("-", text)
    text = re.sub(r"-{2,}", "-", text).strip("-").lower()
    if not text:
        text = "entry"
    if len(text) > max_length:
        text = text[:max_length].rstrip("-")
    return text or "entry"


def ensure_unique_slug(base: str, seen: set[str], *, max_length: int = 80) -> str:
    slug = base[:max_length].rstrip("-") or "entry"
    if slug not in seen:
        seen.add(slug)
        return slug

    index = 2
    while True:
        suffix = f"-{index}"
        candidate = slug[: max_length - len(suffix)].rstrip("-") + suffix
        if candidate not in seen:
            seen.add(candidate)
            return candidate
        index += 1


def parse_page_label_line(value: str | None) -> str | None:
    if not value:
        return None
    match = HYPHEN_LABEL_RE.match(normalize_line(value))
    if not match:
        return None
    label = match.group(1)
    return label.lower() if label.isalpha() else label


def detect_page_label(top_lines: list[str]) -> str | None:
    for line in top_lines[:8]:
        page_label = parse_page_label_line(line)
        if page_label is not None:
            return page_label
    return None


def extract_page_text(page: pymupdf.Page) -> str:
    return page.get_text("text").replace("\x00", " ").strip()


def extract_top_lines(text: str, *, limit: int = 12) -> list[str]:
    lines = [normalize_line(raw_line) for raw_line in str(text).splitlines()]
    return [line for line in lines if line][:limit]


def count_image_blocks(page: pymupdf.Page) -> int:
    return sum(1 for block in extract_page_blocks(page) if block.get("type") == 1)


def extract_page_blocks(page: pymupdf.Page) -> list[dict[str, Any]]:
    return page.get_text("dict").get("blocks", [])


def text_block_to_text(block: dict[str, Any]) -> str:
    lines: list[str] = []
    for line in block.get("lines", []):
        spans = [span.get("text", "") for span in line.get("spans", [])]
        joined = normalize_line("".join(spans))
        if joined:
            lines.append(joined)
    return "\n".join(lines)


def extract_page_text_blocks(page: pymupdf.Page) -> list[dict[str, Any]]:
    return [block for block in extract_page_blocks(page) if block.get("type") == 0]


def blocks_to_text(blocks: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for block in blocks:
        if block.get("type") != 0:
            continue
        text = text_block_to_text(block)
        if text:
            parts.append(text)
    return "\n\n".join(parts).strip()


def build_label_to_page_map(inventory: dict[str, Any]) -> dict[str, int]:
    mapping: dict[str, int] = {}
    for page in inventory.get("pages", []):
        page_label = page.get("pageLabel")
        page_number = page.get("pageNumber")
        if page_label and page_number and page_label not in mapping:
            mapping[str(page_label)] = int(page_number)
    return mapping


def strip_page_label_line(lines: list[str]) -> list[str]:
    return [line for line in lines if parse_page_label_line(line) is None]


def strip_running_header_lines(lines: list[str]) -> list[str]:
    filtered = [line for line in lines if not any(pattern.match(line) for pattern in RUNNING_HEADER_PATTERNS)]

    while len(filtered) >= 3 and filtered[0] == "제" and filtered[1].isdigit() and filtered[2] == "편":
        filtered = filtered[3:]

    result: list[str] = []
    for index, line in enumerate(filtered):
        if (
            index < 6
            and STRUCTURAL_HEADING_RE.match(line)
            and any(line == filtered[next_index] for next_index in range(index + 1, min(len(filtered), index + 4)))
        ):
            continue
        result.append(line)

    return result


def page_text_to_paragraphs(text: str) -> list[str]:
    raw_lines = [normalize_line(line) for line in text.splitlines()]
    lines = [line for line in strip_running_header_lines(strip_page_label_line(raw_lines)) if line]
    if not lines:
        return []

    paragraphs: list[str] = []
    buffer: list[str] = []
    for line in lines:
        if not line:
            if buffer:
                paragraphs.append(" ".join(buffer))
                buffer = []
            continue
        buffer.append(line)
        if len(" ".join(buffer)) >= 420:
            paragraphs.append(" ".join(buffer))
            buffer = []

    if buffer:
        paragraphs.append(" ".join(buffer))

    return paragraphs


def make_excerpt(text: str, *, limit: int = 160) -> str:
    normalized = normalize_search_text(text)
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 1].rstrip() + "…"


def paragraph_to_html(paragraph: str) -> str:
    return f"<p>{escape(paragraph)}</p>"


def image_to_html(relative_path: str, alt: str) -> str:
    return (
        '<figure class="reader-figure">'
        f'<img src="./generated/{escape(relative_path)}" alt="{escape(alt)}" loading="lazy" />'
        "</figure>"
    )
