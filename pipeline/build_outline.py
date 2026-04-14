from __future__ import annotations

from typing import Any

from .common import (
    build_label_to_page_map,
    load_config,
    load_generated_json,
    normalize_bookmark_title,
    open_pdf,
    print_json_summary,
    write_json,
)


def collect_outline_entries(document: Any, label_by_page: dict[int, str | None]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    parent_stack: list[dict[str, int]] = []

    for index, raw_entry in enumerate(document.get_toc(), start=1):
        level = int(raw_entry[0])
        title = normalize_bookmark_title(raw_entry[1])
        page_start = int(raw_entry[2])

        while parent_stack and parent_stack[-1]["level"] >= level:
            parent_stack.pop()

        parent_index = parent_stack[-1]["index"] if parent_stack else None
        entry = {
            "index": index,
            "level": level,
            "title": title,
            "pageStart": page_start,
            "pageLabelStart": label_by_page.get(page_start),
            "parentIndex": parent_index,
        }
        entries.append(entry)
        parent_stack.append({"level": level, "index": index})

    return entries


def count_levels(entries: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for entry in entries:
        key = f"level{entry['level']}Count"
        counts[key] = counts.get(key, 0) + 1
    return counts


def main() -> None:
    config = load_config()
    inventory = load_generated_json("pdf-inventory.json")
    document = open_pdf(config)
    label_by_page = {
        int(page["pageNumber"]): page.get("pageLabel")
        for page in inventory.get("pages", [])
    }
    label_map = build_label_to_page_map(inventory)
    entries = collect_outline_entries(document, label_by_page)
    level_counts = count_levels(entries)

    payload = {
        "meta": {
            "title": config["documentTitle"],
            "pageCount": document.page_count,
            "entryCount": len(entries),
            **level_counts,
            "pageLabelCount": len(label_map),
        },
        "entries": entries,
    }
    target = write_json("outline.json", payload)
    print_json_summary(
        "outline",
        {
            "target": str(target),
            "entryCount": len(entries),
            **level_counts,
        },
    )


if __name__ == "__main__":
    main()
