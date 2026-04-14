from __future__ import annotations

import hashlib
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pymupdf

from .common import GENERATED_DIR, load_config, load_generated_json, open_pdf, print_json_summary, write_json


GENERATED_IMAGES_DIR = GENERATED_DIR / "images"
DEFAULT_IMAGE_EXCLUSION = {
    "minDimensionPx": 20,
    "maxPageRepetitions": 12,
    "excludeCoverPages": [1, 2, 3, 4],
    "decorativePageCharCountMax": 40,
    "decorativePageMinImageCount": 2,
}
PRESERVED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg"}


def load_image_exclusion(config: dict[str, Any]) -> dict[str, Any]:
    raw = config.get("imageExclusion", {})
    return {
        "minDimensionPx": int(raw.get("minDimensionPx", DEFAULT_IMAGE_EXCLUSION["minDimensionPx"])),
        "maxPageRepetitions": int(
            raw.get("maxPageRepetitions", DEFAULT_IMAGE_EXCLUSION["maxPageRepetitions"])
        ),
        "excludeCoverPages": [
            int(page_number)
            for page_number in raw.get(
                "excludeCoverPages", DEFAULT_IMAGE_EXCLUSION["excludeCoverPages"]
            )
        ],
        "decorativePageCharCountMax": int(
            raw.get(
                "decorativePageCharCountMax",
                DEFAULT_IMAGE_EXCLUSION["decorativePageCharCountMax"],
            )
        ),
        "decorativePageMinImageCount": int(
            raw.get(
                "decorativePageMinImageCount",
                DEFAULT_IMAGE_EXCLUSION["decorativePageMinImageCount"],
            )
        ),
    }


def prepare_generated_images_dir(images_dir: Path = GENERATED_IMAGES_DIR) -> Path:
    if images_dir.exists():
        shutil.rmtree(images_dir)
    images_dir.mkdir(parents=True, exist_ok=True)
    return images_dir


def is_decorative_page(page_meta: dict[str, Any], exclusion: dict[str, Any]) -> bool:
    return int(page_meta.get("charCount", 0)) <= exclusion["decorativePageCharCountMax"] and int(
        page_meta.get("imageCount", 0)
    ) >= exclusion["decorativePageMinImageCount"]


def should_skip_page(
    page_number: int,
    page_meta: dict[str, Any],
    toc_pages: set[int],
    exclusion: dict[str, Any],
) -> bool:
    return (
        page_number in toc_pages
        or page_number in set(exclusion["excludeCoverPages"])
        or is_decorative_page(page_meta, exclusion)
    )


def should_skip_image_info(info: dict[str, Any], exclusion: dict[str, Any]) -> bool:
    return int(info.get("width", 0)) < exclusion["minDimensionPx"] or int(
        info.get("height", 0)
    ) < exclusion["minDimensionPx"]


def bbox_distance(left: tuple[float, ...], right: tuple[float, ...]) -> float:
    if len(left) != 4 or len(right) != 4:
        return float("inf")
    return sum(abs(float(left[index]) - float(right[index])) for index in range(4))


def match_inline_image_block(
    info: dict[str, Any],
    image_blocks: list[dict[str, Any]],
    used_indices: set[int],
) -> dict[str, Any] | None:
    info_bbox = tuple(float(value) for value in info.get("bbox", ()))
    best_index: int | None = None
    best_score: float | None = None

    for index, block in enumerate(image_blocks):
        if index in used_indices:
            continue
        if int(block.get("width", 0)) != int(info.get("width", 0)):
            continue
        if int(block.get("height", 0)) != int(info.get("height", 0)):
            continue
        block_bbox = tuple(float(value) for value in block.get("bbox", ()))
        score = bbox_distance(block_bbox, info_bbox)
        if best_score is None or score < best_score:
            best_index = index
            best_score = score

    if best_index is None:
        return None

    used_indices.add(best_index)
    return image_blocks[best_index]


def pixmap_to_png_bytes(pixmap: pymupdf.Pixmap) -> bytes:
    color_components = pixmap.n - pixmap.alpha
    if color_components not in (1, 3):
        pixmap = pymupdf.Pixmap(pymupdf.csRGB, pixmap)
    return pixmap.tobytes("png")


def normalize_image_bytes(image_bytes: bytes, ext: str, mask_bytes: bytes | None = None) -> tuple[bytes, str]:
    normalized_ext = (ext or "png").lower()
    if mask_bytes:
        base_pixmap = pymupdf.Pixmap(image_bytes)
        mask_pixmap = pymupdf.Pixmap(mask_bytes)
        return pixmap_to_png_bytes(pymupdf.Pixmap(base_pixmap, mask_pixmap)), "png"
    if normalized_ext in PRESERVED_IMAGE_EXTENSIONS:
        return image_bytes, normalized_ext
    return pixmap_to_png_bytes(pymupdf.Pixmap(image_bytes)), "png"


def extract_export_image(
    document: pymupdf.Document,
    page: pymupdf.Page,
    info: dict[str, Any],
    image_blocks: list[dict[str, Any]] | None,
    used_block_indices: set[int],
) -> tuple[bytes, str]:
    xref = int(info.get("xref") or 0)
    if xref > 0:
        extracted = document.extract_image(xref)
        mask_bytes = None
        smask = int(extracted.get("smask") or 0)
        if smask > 0:
            mask_bytes = document.extract_image(smask)["image"]
        return normalize_image_bytes(extracted["image"], str(extracted.get("ext") or "png"), mask_bytes)

    blocks = image_blocks or [
        block for block in page.get_text("dict").get("blocks", []) if block.get("type") == 1
    ]
    block = match_inline_image_block(info, blocks, used_block_indices)
    if block is None:
        raise SystemExit(
            f"inline image block를 찾을 수 없습니다: page={page.number + 1} number={info.get('number')}"
        )
    return normalize_image_bytes(block["image"], str(block.get("ext") or "png"), block.get("mask"))


def prune_repeated_assets(
    assets_by_hash: dict[str, dict[str, Any]],
    max_page_repetitions: int,
) -> tuple[dict[str, dict[str, Any]], int]:
    kept_assets: dict[str, dict[str, Any]] = {}
    excluded_occurrence_count = 0

    for asset_hash, asset in assets_by_hash.items():
        occurrence_count = len(asset["_pageNumbers"])
        if occurrence_count > max_page_repetitions:
            excluded_occurrence_count += occurrence_count
            continue
        kept_assets[asset_hash] = asset

    return kept_assets, excluded_occurrence_count


def build_manifest_entries(assets_by_hash: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for asset in sorted(
        assets_by_hash.values(),
        key=lambda item: (item["_pageNumbers"][0] if item["_pageNumbers"] else 0, item["id"]),
    ):
        entries.append(
            {
                "id": asset["id"],
                "filename": asset["filename"],
                "relativePath": asset["relativePath"],
                "pageNumbers": sorted(asset["_pageNumbers"]),
                "pageLabels": asset["_pageLabels"],
                "width": asset["width"],
                "height": asset["height"],
                "byteSize": asset["byteSize"],
            }
        )
    return entries


def main() -> None:
    config = load_config()
    exclusion = load_image_exclusion(config)
    inventory = load_generated_json("pdf-inventory.json")
    toc = load_generated_json("toc.json")
    document = open_pdf(config)
    page_lookup = {page["pageNumber"]: page for page in inventory["pages"]}
    toc_pages = set(toc["meta"].get("tocPages", []))
    prepare_generated_images_dir()

    assets_by_hash: dict[str, dict[str, Any]] = {}
    skipped_small_image_count = 0
    skipped_page_image_count = 0

    for page_number in range(1, document.page_count + 1):
        page_meta = page_lookup.get(
            page_number,
            {
                "pageNumber": page_number,
                "pageLabel": None,
                "charCount": 0,
                "imageCount": 0,
            },
        )
        if should_skip_page(page_number, page_meta, toc_pages, exclusion):
            skipped_page_image_count += int(page_meta.get("imageCount", 0))
            continue

        page = document.load_page(page_number - 1)
        image_infos = page.get_image_info(hashes=True, xrefs=True)
        if not image_infos:
            continue

        image_blocks: list[dict[str, Any]] | None = None
        used_block_indices: set[int] = set()

        for info in image_infos:
            if should_skip_image_info(info, exclusion):
                skipped_small_image_count += 1
                continue

            if int(info.get("xref") or 0) == 0 and image_blocks is None:
                image_blocks = [
                    block for block in page.get_text("dict").get("blocks", []) if block.get("type") == 1
                ]

            image_bytes, ext = extract_export_image(
                document=document,
                page=page,
                info=info,
                image_blocks=image_blocks,
                used_block_indices=used_block_indices,
            )
            asset_hash = hashlib.sha1(image_bytes).hexdigest()
            asset = assets_by_hash.get(asset_hash)
            if asset is None:
                short_hash = asset_hash[:12]
                asset = {
                    "id": short_hash,
                    "filename": f"{short_hash}.{ext}",
                    "relativePath": f"images/{short_hash}.{ext}",
                    "width": int(info.get("width") or 0),
                    "height": int(info.get("height") or 0),
                    "byteSize": len(image_bytes),
                    "_bytes": image_bytes,
                    "_pageNumbers": [],
                    "_pageLabels": [],
                }
                assets_by_hash[asset_hash] = asset

            if page_number not in asset["_pageNumbers"]:
                asset["_pageNumbers"].append(page_number)
            page_label = page_meta.get("pageLabel")
            if page_label and page_label not in asset["_pageLabels"]:
                asset["_pageLabels"].append(page_label)

    assets_by_hash, skipped_repeated_image_count = prune_repeated_assets(
        assets_by_hash,
        exclusion["maxPageRepetitions"],
    )

    for asset in assets_by_hash.values():
        (GENERATED_IMAGES_DIR / asset["filename"]).write_bytes(asset["_bytes"])

    manifest_entries = build_manifest_entries(assets_by_hash)
    manifest = {
        "meta": {
            "title": config["documentTitle"],
            "builtAt": datetime.now(UTC).isoformat(),
            "imageCount": len(manifest_entries),
        },
        "images": manifest_entries,
    }
    target = write_json("image-manifest.json", manifest)
    print_json_summary(
        "images",
        {
            "target": str(target),
            "imageCount": len(manifest_entries),
            "skippedSmallImageCount": skipped_small_image_count,
            "skippedPageImageCount": skipped_page_image_count,
            "skippedRepeatedImageCount": skipped_repeated_image_count,
        },
    )


if __name__ == "__main__":
    main()
