from __future__ import annotations

import json
import shutil
import re
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from .common import (
    DATA_DIR,
    GENERATED_DIR,
    fail,
    load_config,
    normalize_bookmark_title,
    normalize_search_text,
    print_json_summary,
    slugify,
)


NOTEBOOKLM_DIR = DATA_DIR / "notebooklm"

SECTION_RE = re.compile(r'<section\s+id="([^"]+)">(.*?)</section>', re.DOTALL)

ALWAYS_INCLUDED_CHAPTER_SLUGS = {"front-preface", "front-notes"}
ALWAYS_EXCLUDED_CHAPTER_SLUGS = {"cover-and-masthead", "editorial-board"}
ALWAYS_EXCLUDED_PART_TITLES = {"부 록", "후면부"}
SKIPPED_SECTION_IDS = {"part-intro"}


class MarkdownFragmentParser(HTMLParser):
    def __init__(self, *, chapter_title: str, chapter_heading_level: int) -> None:
        super().__init__(convert_charrefs=True)
        self.chapter_title = normalize_bookmark_title(chapter_title)
        self.chapter_heading_level = int(chapter_heading_level)
        self.blocks: list[str] = []
        self.current_tag: str | None = None
        self.current_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"h2", "h3", "h4", "p"}:
            self._flush_current()
            self.current_tag = tag
            self.current_text = []
            return

        if tag == "img":
            attributes = dict(attrs)
            alt = normalize_search_text(attributes.get("alt") or "이미지")
            self.blocks.append(f"[이미지 생략: {alt}]")

    def handle_endtag(self, tag: str) -> None:
        if tag == self.current_tag:
            self._flush_current()

    def handle_data(self, data: str) -> None:
        if self.current_tag is not None:
            self.current_text.append(data)

    def close(self) -> None:
        super().close()
        self._flush_current()

    def _flush_current(self) -> None:
        if self.current_tag is None:
            return

        text = normalize_search_text("".join(self.current_text))
        tag = self.current_tag
        self.current_tag = None
        self.current_text = []
        if not text:
            return

        if tag == "p":
            self.blocks.append(text)
            return

        if tag == "h2":
            if normalize_bookmark_title(text) == self.chapter_title:
                return
            level = self.chapter_heading_level
        elif tag == "h3":
            level = self.chapter_heading_level + 1
        else:
            level = self.chapter_heading_level + 2

        self.blocks.append(f"{'#' * level} {text}")


def split_html_sections(html: str) -> list[dict[str, str | None]]:
    sections = [
        {"id": match.group(1), "html": match.group(2)}
        for match in SECTION_RE.finditer(str(html))
    ]
    if sections:
        return sections
    return [{"id": None, "html": str(html)}]


def render_html_fragment_to_markdown(
    html: str,
    *,
    chapter_title: str,
    chapter_heading_level: int,
) -> str:
    parser = MarkdownFragmentParser(
        chapter_title=chapter_title,
        chapter_heading_level=chapter_heading_level,
    )
    parser.feed(str(html))
    parser.close()
    return "\n\n".join(block for block in parser.blocks if block).strip()


def build_section_title_lookup(chapter: dict[str, Any]) -> dict[str, str]:
    lookup = {"overview": "개요"}
    for heading in chapter.get("headings", []):
        lookup[str(heading["id"])] = normalize_bookmark_title(heading["title"])
    return lookup


def build_review_queue_map(review_queue: dict[str, Any]) -> dict[str, dict[str, Any]]:
    chapters: dict[str, dict[str, Any]] = {}
    for item in review_queue.get("queue", []):
        chapter_slug = str(item["chapterSlug"])
        section_id = str(item["sectionId"])
        chapter_entry = chapters.setdefault(
            chapter_slug,
            {
                "pageNumbers": set(),
                "pageLabels": set(),
                "flags": set(),
                "sections": {},
            },
        )
        chapter_entry["pageNumbers"].add(int(item["pageNumber"]))
        if item.get("pageLabel"):
            chapter_entry["pageLabels"].add(str(item["pageLabel"]))
        chapter_entry["flags"].update(str(flag) for flag in item.get("flags", []))

        section_entry = chapter_entry["sections"].setdefault(
            section_id,
            {
                "pageNumbers": set(),
                "pageLabels": set(),
                "flags": set(),
            },
        )
        section_entry["pageNumbers"].add(int(item["pageNumber"]))
        if item.get("pageLabel"):
            section_entry["pageLabels"].add(str(item["pageLabel"]))
        section_entry["flags"].update(str(flag) for flag in item.get("flags", []))

    finalized: dict[str, dict[str, Any]] = {}
    for chapter_slug, chapter_entry in chapters.items():
        finalized[chapter_slug] = {
            "pageNumbers": sorted(chapter_entry["pageNumbers"]),
            "pageLabels": sorted(chapter_entry["pageLabels"]),
            "flags": sorted(chapter_entry["flags"]),
            "sections": {
                section_id: {
                    "pageNumbers": sorted(section_entry["pageNumbers"]),
                    "pageLabels": sorted(section_entry["pageLabels"]),
                    "flags": sorted(section_entry["flags"]),
                }
                for section_id, section_entry in chapter_entry["sections"].items()
            },
        }
    return finalized


def format_range(start: str | int | None, end: str | int | None) -> str:
    if start in (None, "") and end in (None, ""):
        return "-"
    if start == end or end in (None, ""):
        return str(start)
    if start in (None, ""):
        return str(end)
    return f"{start}-{end}"


def format_locator(chapter: dict[str, Any]) -> str:
    label_range = format_range(chapter.get("pageLabelStart"), chapter.get("pageLabelEnd"))
    pdf_range = format_range(chapter.get("pageStart"), chapter.get("pageEnd"))
    if label_range == "-":
        return f"PDF {pdf_range}"
    return f"인쇄 {label_range} / PDF {pdf_range}"


def summarize_review_info(review_info: dict[str, Any]) -> str:
    parts: list[str] = []
    if review_info.get("pageLabels"):
        parts.append("인쇄 " + ", ".join(review_info["pageLabels"]))
    if review_info.get("pageNumbers"):
        parts.append("PDF " + ", ".join(str(page) for page in review_info["pageNumbers"]))
    if review_info.get("flags"):
        parts.append("flags: " + ", ".join(review_info["flags"]))
    return "; ".join(parts)


def build_section_omission_note(section_title: str, review_info: dict[str, Any]) -> str:
    details = summarize_review_info(review_info)
    base = f"> 생략: {section_title} section은 고위험 페이지 검토 항목 때문에 NotebookLM v1에서 제외했습니다."
    if not details:
        return base
    return f"{base} ({details})"


def build_excluded_chapter_reason(
    chapter: dict[str, Any],
    *,
    review_info: dict[str, Any] | None = None,
) -> str:
    slug = str(chapter["slug"])
    part_title = str(chapter["partTitle"])
    if slug == "cover-and-masthead":
        return "표지성 전면부 콘텐츠라서 NotebookLM v1에서 제외했습니다."
    if slug == "editorial-board" or part_title == "후면부":
        return "후면부 관리성 콘텐츠라서 NotebookLM v1에서 제외했습니다."
    if part_title == "부 록":
        return "부록은 표/서식 의존도가 높아 NotebookLM v1에서 제외했습니다."
    if review_info is None:
        return "NotebookLM v1 제외 정책에 따라 제외했습니다."
    details = summarize_review_info(review_info)
    base = "고위험 페이지가 있으나 section heading이 없어 chapter 전체를 NotebookLM v1에서 제외했습니다."
    if not details:
        return base
    return f"{base} ({details})"


def build_excluded_record(
    chapter: dict[str, Any],
    reason: str,
    *,
    kind: str = "chapter",
    section_id: str | None = None,
    section_title: str | None = None,
) -> dict[str, Any]:
    return {
        "kind": kind,
        "partTitle": str(chapter["partTitle"]),
        "chapterSlug": str(chapter["slug"]),
        "chapterTitle": normalize_bookmark_title(chapter["title"]),
        "sectionId": section_id,
        "sectionTitle": section_title,
        "pageStart": int(chapter["pageStart"]),
        "pageEnd": int(chapter["pageEnd"]),
        "pageLabelStart": chapter.get("pageLabelStart"),
        "pageLabelEnd": chapter.get("pageLabelEnd"),
        "reason": reason,
    }


def build_part_order(chapters: list[dict[str, Any]]) -> list[str]:
    order: list[str] = []
    seen: set[str] = set()
    for chapter in chapters:
        part_title = str(chapter["partTitle"])
        if part_title in ALWAYS_EXCLUDED_PART_TITLES or part_title in seen:
            continue
        seen.add(part_title)
        order.append(part_title)
    return order


def render_chapter_body(
    chapter: dict[str, Any],
    *,
    excluded_section_ids: set[str],
    review_map: dict[str, Any],
    chapter_heading_level: int,
) -> tuple[str, list[dict[str, Any]]]:
    section_lookup = build_section_title_lookup(chapter)
    chunks: list[str] = []
    omitted_records: list[dict[str, Any]] = []
    for section in split_html_sections(chapter["html"]):
        section_id = str(section["id"]) if section["id"] is not None else None
        if section_id in SKIPPED_SECTION_IDS:
            continue
        if section_id and section_id in excluded_section_ids:
            section_title = section_lookup.get(section_id, normalize_bookmark_title(section_id))
            review_info = review_map["sections"].get(section_id, {})
            chunks.append(build_section_omission_note(section_title, review_info))
            omitted_records.append(
                build_excluded_record(
                    chapter,
                    build_section_omission_note(section_title, review_info).removeprefix("> ").strip(),
                    kind="section",
                    section_id=section_id,
                    section_title=section_title,
                )
            )
            continue

        rendered = render_html_fragment_to_markdown(
            section["html"] or "",
            chapter_title=chapter["title"],
            chapter_heading_level=chapter_heading_level,
        )
        if rendered:
            chunks.append(rendered)

    return "\n\n".join(chunk for chunk in chunks if chunk).strip(), omitted_records


def render_chapter_document(
    chapter: dict[str, Any],
    *,
    body_markdown: str,
    omitted_section_count: int,
    chapter_heading_level: int,
    include_part_metadata: bool,
    qa_override_note: str | None = None,
) -> str:
    lines = [f"{'#' * chapter_heading_level} {normalize_bookmark_title(chapter['title'])}", ""]
    if include_part_metadata:
        lines.append(f"- 편: {normalize_bookmark_title(chapter['partTitle'])}")
    lines.append(f"- 범위: {format_locator(chapter)}")
    if omitted_section_count:
        lines.append(f"- 생략: 위험 section {omitted_section_count}개")
    if qa_override_note:
        lines.append(f"- 참고: {qa_override_note}")
    lines.append("")
    lines.append(body_markdown or "NotebookLM v1에서 포함 가능한 본문이 없습니다.")
    return "\n".join(lines).strip() + "\n"


def count_words(value: str) -> int:
    return len(str(value).split())


def write_text(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8")
    return path


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def prepare_output_dir(output_dir: Path) -> tuple[Path, Path]:
    if output_dir.exists():
        shutil.rmtree(output_dir)
    parts_dir = output_dir / "parts"
    chapters_dir = output_dir / "chapters"
    parts_dir.mkdir(parents=True, exist_ok=True)
    chapters_dir.mkdir(parents=True, exist_ok=True)
    return parts_dir, chapters_dir


def export_notebooklm_sources(
    *,
    generated_dir: Path = GENERATED_DIR,
    output_dir: Path = NOTEBOOKLM_DIR,
    title: str | None = None,
    slug_max_length: int = 80,
) -> dict[str, Any]:
    document_path = generated_dir / "document-data.json"
    queue_path = generated_dir / "page-review-queue.json"
    if not document_path.exists() or not queue_path.exists():
        fail(
            "NotebookLM export에 필요한 generated 파일이 없습니다. 먼저 `npm run content:prepare`를 실행하세요."
        )

    document_data = read_json(document_path)
    review_queue = read_json(queue_path)
    document_title = title or str(document_data.get("meta", {}).get("title") or "NotebookLM Sources")
    chapters = list(document_data.get("chapters", []))
    review_map_by_chapter = build_review_queue_map(review_queue)
    part_order = build_part_order(chapters)

    parts_dir, chapters_dir = prepare_output_dir(output_dir)
    part_buckets: dict[str, dict[str, list[dict[str, Any]]]] = {
        part_title: {
            "included": [],
            "excludedChapters": [],
            "omittedSections": [],
        }
        for part_title in part_order
    }

    chapter_file_count = 0
    chapter_prefix = 1
    excluded_chapters: list[dict[str, Any]] = []
    omitted_sections: list[dict[str, Any]] = []

    for chapter in chapters:
        part_title = str(chapter["partTitle"])
        review_map = review_map_by_chapter.get(str(chapter["slug"]), {"sections": {}, "pageNumbers": [], "pageLabels": [], "flags": []})

        if str(chapter["slug"]) in ALWAYS_EXCLUDED_CHAPTER_SLUGS or part_title in ALWAYS_EXCLUDED_PART_TITLES:
            record = build_excluded_record(chapter, build_excluded_chapter_reason(chapter))
            excluded_chapters.append(record)
            if part_title in part_buckets:
                part_buckets[part_title]["excludedChapters"].append(record)
            continue

        headings = list(chapter.get("headings", []))
        risky_section_ids = set(review_map.get("sections", {}).keys())
        force_include = str(chapter["slug"]) in ALWAYS_INCLUDED_CHAPTER_SLUGS
        if risky_section_ids and not headings and not force_include:
            record = build_excluded_record(
                chapter,
                build_excluded_chapter_reason(chapter, review_info=review_map),
            )
            excluded_chapters.append(record)
            if part_title in part_buckets:
                part_buckets[part_title]["excludedChapters"].append(record)
            continue

        excluded_section_ids = risky_section_ids if headings else set()
        body_markdown, chapter_omitted_records = render_chapter_body(
            chapter,
            excluded_section_ids=excluded_section_ids,
            review_map=review_map,
            chapter_heading_level=1,
        )
        part_body_markdown, _ = render_chapter_body(
            chapter,
            excluded_section_ids=excluded_section_ids,
            review_map=review_map,
            chapter_heading_level=2,
        )
        omitted_sections.extend(chapter_omitted_records)
        if part_title in part_buckets:
            part_buckets[part_title]["omittedSections"].extend(chapter_omitted_records)

        qa_override_note = None
        if force_include and risky_section_ids and not headings:
            qa_override_note = "전면부 포함 정책에 따라 QA 위험 페이지가 있어도 chapter 전체를 유지했습니다."

        chapter_markdown = render_chapter_document(
            chapter,
            body_markdown=body_markdown,
            omitted_section_count=len(chapter_omitted_records),
            chapter_heading_level=1,
            include_part_metadata=True,
            qa_override_note=qa_override_note,
        )
        part_chapter_markdown = render_chapter_document(
            chapter,
            body_markdown=part_body_markdown,
            omitted_section_count=len(chapter_omitted_records),
            chapter_heading_level=2,
            include_part_metadata=False,
            qa_override_note=qa_override_note,
        )

        chapter_filename = f"{chapter_prefix:03d}__{slugify(chapter['slug'], max_length=slug_max_length)}.md"
        chapter_path = chapters_dir / chapter_filename
        write_text(chapter_path, chapter_markdown)
        chapter_file_count += 1
        chapter_prefix += 1

        chapter_entry = {
            "filename": chapter_filename,
            "path": str(chapter_path),
            "slug": str(chapter["slug"]),
            "title": normalize_bookmark_title(chapter["title"]),
            "partTitle": normalize_bookmark_title(part_title),
            "locator": format_locator(chapter),
            "omittedSectionCount": len(chapter_omitted_records),
            "partMarkdown": part_chapter_markdown.strip(),
            "wordCount": count_words(part_chapter_markdown),
        }
        if part_title in part_buckets:
            part_buckets[part_title]["included"].append(chapter_entry)

    part_summaries: list[dict[str, Any]] = []
    max_part_word_count = 0
    for index, part_title in enumerate(part_order, start=1):
        bucket = part_buckets[part_title]
        part_slug = slugify(part_title, max_length=slug_max_length)
        filename = f"{index:02d}__{part_slug}.md"
        part_path = parts_dir / filename

        lines = [f"# {normalize_bookmark_title(part_title)}", ""]
        lines.append("## 포함 장")
        if bucket["included"]:
            for chapter_entry in bucket["included"]:
                lines.append(f"- {chapter_entry['title']} ({chapter_entry['locator']})")
        else:
            lines.append("- 없음")
        lines.append("")
        lines.append("## 제외/생략")
        exclusion_lines: list[str] = []
        for record in bucket["excludedChapters"]:
            exclusion_lines.append(
                f"- {record['chapterTitle']}: {record['reason']}"
            )
        for record in bucket["omittedSections"]:
            exclusion_lines.append(
                f"- {record['chapterTitle']} > {record['sectionTitle']}: {record['reason']}"
            )
        if exclusion_lines:
            lines.extend(exclusion_lines)
        else:
            lines.append("- 없음")
        lines.append("")
        lines.append("## 본문")
        lines.append("")
        if bucket["included"]:
            for position, chapter_entry in enumerate(bucket["included"]):
                lines.append(chapter_entry["partMarkdown"])
                if position != len(bucket["included"]) - 1:
                    lines.extend(["", "---", ""])
        else:
            lines.append("이 편은 NotebookLM v1에서 포함 가능한 장이 없습니다. 제외 사유는 위 목록을 참고하세요.")

        part_markdown = "\n".join(lines).strip() + "\n"
        write_text(part_path, part_markdown)
        part_word_count = count_words(part_markdown)
        max_part_word_count = max(max_part_word_count, part_word_count)
        part_summaries.append(
            {
                "filename": filename,
                "path": str(part_path),
                "partTitle": normalize_bookmark_title(part_title),
                "includedChapterCount": len(bucket["included"]),
                "excludedChapterCount": len(bucket["excludedChapters"]),
                "omittedSectionCount": len(bucket["omittedSections"]),
                "wordCount": part_word_count,
            }
        )

    excluded_lines = [f"# {document_title} NotebookLM 제외/생략 내역", ""]
    excluded_lines.append("## Chapter 제외")
    if excluded_chapters:
        for record in excluded_chapters:
            excluded_lines.append(
                f"- {record['partTitle']} / {record['chapterTitle']} ({format_range(record['pageLabelStart'], record['pageLabelEnd'])} / PDF {record['pageStart']}-{record['pageEnd']}): {record['reason']}"
            )
    else:
        excluded_lines.append("- 없음")
    excluded_lines.append("")
    excluded_lines.append("## Section 생략")
    if omitted_sections:
        for record in omitted_sections:
            excluded_lines.append(
                f"- {record['partTitle']} / {record['chapterTitle']} > {record['sectionTitle']}: {record['reason']}"
            )
    else:
        excluded_lines.append("- 없음")
    excluded_path = write_text(output_dir / "excluded.md", "\n".join(excluded_lines))

    index_lines = [f"# {document_title} NotebookLM Source Index", ""]
    index_lines.extend(
        [
            f"- 생성 시각: {datetime.now(UTC).isoformat()}",
            f"- 업로드용 part 파일 수: {len(part_summaries)}",
            f"- 검수용 chapter 파일 수: {chapter_file_count}",
            f"- chapter 제외 수: {len(excluded_chapters)}",
            f"- section 생략 수: {len(omitted_sections)}",
            f"- 최대 part 단어 수: {max_part_word_count}",
            "",
            "## 업로드 순서",
        ]
    )
    for summary in part_summaries:
        index_lines.append(
            f"- {summary['filename']}: {summary['partTitle']} / 포함 장 {summary['includedChapterCount']}개 / 제외 장 {summary['excludedChapterCount']}개 / 생략 section {summary['omittedSectionCount']}개 / {summary['wordCount']} words"
        )
    index_lines.append("")
    index_lines.append("## 참고")
    index_lines.append(f"- 제외/생략 ledger: {excluded_path.name}")
    index_lines.append("- `parts/`는 NotebookLM 업로드용, `chapters/`는 검수/디버깅용입니다.")
    index_path = write_text(output_dir / "index.md", "\n".join(index_lines))

    return {
        "outputDir": str(output_dir),
        "indexPath": str(index_path),
        "excludedPath": str(excluded_path),
        "partFileCount": len(part_summaries),
        "chapterFileCount": chapter_file_count,
        "excludedChapterCount": len(excluded_chapters),
        "omittedSectionCount": len(omitted_sections),
        "maxPartWordCount": max_part_word_count,
        "partSummaries": part_summaries,
    }


def main() -> None:
    config = load_config()
    summary = export_notebooklm_sources(
        title=config.get("documentTitle"),
        slug_max_length=int(config.get("slugMaxLength", 80)),
    )
    print_json_summary("notebooklm-export", summary)


if __name__ == "__main__":
    main()
