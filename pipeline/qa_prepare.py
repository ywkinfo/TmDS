from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from .common import ROOT_DIR, load_config, load_generated_json, open_pdf, print_json_summary, write_json
from .review_layout import build_page_review_entries, prepare_review_pages_dir, render_review_page_image


WEB_GENERATED_DIR = ROOT_DIR / "web" / "public" / "generated"
WEB_REVIEW_PAGES_DIR = WEB_GENERATED_DIR / "review-pages"


def resolve_page_locator(page_number: int, search_index: list[dict[str, Any]]) -> tuple[str | None, str | None]:
    candidates = [
        entry
        for entry in search_index
        if int(entry["pageStart"]) <= page_number <= int(entry["pageEnd"])
    ]
    if not candidates:
        return None, None

    priority = {"item": 0, "part-intro": 1, "overview": 2}
    candidates.sort(
        key=lambda entry: (
            priority.get(str(entry.get("entryType")), 9),
            int(entry["pageEnd"]) - int(entry["pageStart"]),
        )
    )
    best = candidates[0]
    return best.get("chapterSlug"), best.get("sectionId")


def sync_review_assets_to_web(page_review: list[dict[str, Any]], source_dir: Path) -> None:
    WEB_GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    (WEB_GENERATED_DIR / "page-review.json").write_text(
        json.dumps(page_review, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    if WEB_REVIEW_PAGES_DIR.exists():
        shutil.rmtree(WEB_REVIEW_PAGES_DIR)
    shutil.copytree(source_dir, WEB_REVIEW_PAGES_DIR)


def main() -> None:
    config = load_config()
    inventory = load_generated_json("pdf-inventory.json")
    search_index = load_generated_json("search-index.json")
    document = open_pdf(config)
    raw_entries = build_page_review_entries(document, inventory)

    review_pages_dir = prepare_review_pages_dir()
    page_review: list[dict[str, Any]] = []

    for entry in raw_entries:
        page_number = int(entry["pageNumber"])
        chapter_slug, section_id = resolve_page_locator(page_number, search_index)
        page_review.append(
            {
                **entry,
                "chapterSlug": chapter_slug,
                "sectionId": section_id,
            }
        )

        target = review_pages_dir / f"{page_number:04d}.jpg"
        render_review_page_image(document.load_page(page_number - 1), target)

    target = write_json("page-review.json", page_review)
    sync_review_assets_to_web(page_review, review_pages_dir)
    print_json_summary(
        "qa-prepare",
        {
            "target": str(target),
            "pageCount": len(page_review),
            "reviewPagesDir": str(review_pages_dir),
            "webReviewPagesDir": str(WEB_REVIEW_PAGES_DIR),
        },
    )


if __name__ == "__main__":
    main()
