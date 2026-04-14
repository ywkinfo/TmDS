from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .common import GENERATED_DIR, ROOT_DIR, fail, load_config, print_json_summary


WEB_GENERATED_DIR = ROOT_DIR / "web" / "public" / "generated"
WEB_GENERATED_IMAGES_DIR = WEB_GENERATED_DIR / "images"
SYNC_FILENAMES = (
    "toc.json",
    "document-data.json",
    "search-index.json",
    "exploration-index.json",
)


def build_sync_plan(
    source_dir: Path = GENERATED_DIR,
    target_dir: Path = WEB_GENERATED_DIR,
    filenames: tuple[str, ...] = SYNC_FILENAMES,
) -> list[dict[str, Path | str]]:
    return [
        {
            "name": filename,
            "source": source_dir / filename,
            "target": target_dir / filename,
        }
        for filename in filenames
    ]


def build_manifest(title: str, file_entries: list[dict[str, Any]], image_file_count: int = 0) -> dict[str, Any]:
    return {
        "title": title,
        "syncedAt": datetime.now(UTC).isoformat(),
        "fileCount": len(file_entries),
        "imageFileCount": image_file_count,
        "files": file_entries,
    }


def write_manifest(target_dir: Path, manifest: dict[str, Any]) -> Path:
    target_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = target_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest_path


def sync_generated_files(
    source_dir: Path = GENERATED_DIR,
    target_dir: Path = WEB_GENERATED_DIR,
    title: str = "Generated Content",
) -> dict[str, Any]:
    plan = build_sync_plan(source_dir=source_dir, target_dir=target_dir)
    missing = [str(item["source"]) for item in plan if not Path(item["source"]).exists()]
    if missing:
        fail(
            "웹 리더용 generated 파일이 없습니다. 먼저 `npm run content:prepare`를 실행하세요.\n- "
            + "\n- ".join(missing)
        )

    target_dir.mkdir(parents=True, exist_ok=True)
    file_entries: list[dict[str, Any]] = []
    for item in plan:
        source = Path(item["source"])
        target = Path(item["target"])
        shutil.copy2(source, target)
        stats = target.stat()
        file_entries.append(
            {
                "name": str(item["name"]),
                "relativePath": f"public/generated/{target.name}",
                "bytes": stats.st_size,
                "modifiedAt": datetime.fromtimestamp(stats.st_mtime, UTC).isoformat(),
            }
        )

    source_images_dir = source_dir / "images"
    if not source_images_dir.exists():
        fail(
            "웹 리더용 generated 이미지 디렉터리가 없습니다. 먼저 `npm run content:prepare`를 실행하세요.\n- "
            + str(source_images_dir)
        )

    target_images_dir = target_dir / "images"
    if target_images_dir.exists():
        shutil.rmtree(target_images_dir)
    shutil.copytree(source_images_dir, target_images_dir)
    image_file_count = sum(1 for path in target_images_dir.rglob("*") if path.is_file())

    manifest = build_manifest(title=title, file_entries=file_entries, image_file_count=image_file_count)
    manifest_path = write_manifest(target_dir=target_dir, manifest=manifest)
    return {
        "targetDir": str(target_dir),
        "fileCount": len(file_entries),
        "imageFileCount": image_file_count,
        "manifestPath": str(manifest_path),
    }


def main() -> None:
    config = load_config()
    summary = sync_generated_files(title=config["documentTitle"])
    print_json_summary("web-sync", summary)


if __name__ == "__main__":
    main()
