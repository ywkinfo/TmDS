from __future__ import annotations

from typing import Any

from .common import load_config, load_generated_json, normalize_space, print_json_summary, write_json


def looks_like_toc_text(value: str) -> bool:
    normalized = normalize_space(value)
    return normalized.startswith("목 차") or normalized.startswith("목차")


def collect_uncovered_body_pages(
    inventory: dict[str, Any],
    search_index: list[dict[str, Any]],
    toc_pages: set[int],
) -> list[int]:
    covered_pages: set[int] = set()
    for entry in search_index:
        for page_number in range(int(entry["pageStart"]), int(entry["pageEnd"]) + 1):
            covered_pages.add(page_number)

    uncovered: list[int] = []
    for page in inventory.get("pages", []):
        page_number = int(page["pageNumber"])
        if page_number in toc_pages:
            continue
        if page.get("pageKind") != "body":
            continue
        if not page.get("hasText"):
            continue
        if page_number not in covered_pages:
            uncovered.append(page_number)
    return uncovered


def main() -> None:
    config = load_config()
    expected = config["expectedStructure"]
    inventory = load_generated_json("pdf-inventory.json")
    outline = load_generated_json("outline.json")
    toc = load_generated_json("toc.json")
    document_data = load_generated_json("document-data.json")
    search_index = load_generated_json("search-index.json")
    exploration_index = load_generated_json("exploration-index.json")
    image_manifest = load_generated_json("image-manifest.json")
    toc_pages = set(int(page_number) for page_number in toc["meta"].get("tocPages", []))

    errors: list[str] = []

    if int(inventory["meta"]["pageCount"]) != int(expected["pageCount"]):
        errors.append(
            f"pageCount mismatch: expected {expected['pageCount']}, got {inventory['meta']['pageCount']}"
        )
    if int(outline["meta"]["level2Count"]) != int(expected["level2Count"]):
        errors.append(
            f"level2Count mismatch: expected {expected['level2Count']}, got {outline['meta']['level2Count']}"
        )
    if int(outline["meta"]["level3Count"]) != int(expected["level3Count"]):
        errors.append(
            f"level3Count mismatch: expected {expected['level3Count']}, got {outline['meta']['level3Count']}"
        )
    if int(outline["meta"]["level4Count"]) != int(expected["level4Count"]):
        errors.append(
            f"level4Count mismatch: expected {expected['level4Count']}, got {outline['meta']['level4Count']}"
        )
    if int(outline["meta"]["entryCount"]) != int(expected["outlineCount"]):
        errors.append(
            f"outlineCount mismatch: expected {expected['outlineCount']}, got {outline['meta']['entryCount']}"
        )

    if not search_index:
        errors.append("search-index.json이 비어 있습니다.")

    for entry in outline.get("entries", []):
        page_start = int(entry["pageStart"])
        if page_start < 1 or page_start > int(expected["pageCount"]):
            errors.append(f"outline pageStart out of range: {entry['title']} -> {page_start}")

    for chapter in document_data.get("chapters", []):
        if looks_like_toc_text(chapter.get("summary", "")):
            errors.append(f"chapter summary leaks toc text: {chapter['slug']}")

    for entry in search_index:
        if not normalize_space(entry.get("text", "")):
            errors.append(f"empty search text: {entry['id']}")
        if int(entry["pageStart"]) in toc_pages:
            errors.append(f"search entry starts on toc page: {entry['id']}")
        if looks_like_toc_text(entry.get("excerpt", "")):
            errors.append(f"search excerpt leaks toc text: {entry['id']}")

    uncovered_body_pages = collect_uncovered_body_pages(inventory, search_index, toc_pages)

    coverage = {
        "pageCount": inventory["meta"]["pageCount"],
        "outlineCount": outline["meta"]["entryCount"],
        "tocPageCount": len(toc_pages),
        "uncoveredBodyPages": uncovered_body_pages,
        "uncoveredBodyPageCount": len(uncovered_body_pages),
        "imageFileCount": len(image_manifest.get("images", [])),
        "searchEntryCount": len(search_index),
        "explorationEntryCount": len(exploration_index),
        "errors": errors,
    }
    target = write_json("coverage-report.json", coverage)
    print_json_summary(
        "qa",
        {
            "target": str(target),
            "errorCount": len(errors),
            "uncoveredBodyPageCount": len(uncovered_body_pages),
        },
    )
    if errors:
        raise SystemExit("\n".join(errors))


if __name__ == "__main__":
    main()
