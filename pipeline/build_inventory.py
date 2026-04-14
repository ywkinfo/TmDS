from __future__ import annotations

from .common import (
    count_image_blocks,
    detect_page_label,
    extract_page_text,
    extract_top_lines,
    load_config,
    open_pdf,
    print_json_summary,
    write_json,
)


def classify_page_kind(page_label: str | None) -> str:
    if page_label is None:
        return "unlabeled"
    if page_label.isdigit():
        return "body"
    return "frontmatter"


def main() -> None:
    config = load_config()
    document = open_pdf(config)
    pages: list[dict[str, object]] = []
    image_pages = 0
    empty_pages = 0

    for index in range(document.page_count):
        page = document.load_page(index)
        page_number = index + 1
        text = extract_page_text(page)
        top_lines = extract_top_lines(text)
        page_label = detect_page_label(top_lines)
        image_count = count_image_blocks(page)

        if image_count:
            image_pages += 1
        if not text:
            empty_pages += 1

        pages.append(
            {
                "pageNumber": page_number,
                "pageLabel": page_label,
                "pageKind": classify_page_kind(page_label),
                "charCount": len(text),
                "imageCount": image_count,
                "hasText": bool(text),
                "topLines": top_lines,
            }
        )

    payload = {
        "meta": {
            "title": config["documentTitle"],
            "pageCount": document.page_count,
            "imagePageCount": image_pages,
            "emptyPageCount": empty_pages,
        },
        "pages": pages,
    }
    target = write_json("pdf-inventory.json", payload)
    print_json_summary(
        "inventory",
        {
            "target": str(target),
            "pageCount": document.page_count,
            "imagePageCount": image_pages,
            "emptyPageCount": empty_pages,
        },
    )


if __name__ == "__main__":
    main()
