from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from pipeline.sync_web_generated import SYNC_FILENAMES, build_manifest, sync_generated_files


class SyncWebGeneratedTest(unittest.TestCase):
    def test_build_manifest_tracks_file_entries(self) -> None:
        manifest = build_manifest(
            title="상표심사기준",
            image_file_count=2,
            file_entries=[
                {
                    "name": "document-data.json",
                    "relativePath": "public/generated/document-data.json",
                    "bytes": 128,
                    "modifiedAt": "2026-04-11T00:00:00+00:00",
                }
            ],
        )

        self.assertEqual(manifest["title"], "상표심사기준")
        self.assertEqual(manifest["fileCount"], 1)
        self.assertEqual(manifest["imageFileCount"], 2)
        self.assertEqual(manifest["files"][0]["name"], "document-data.json")
        self.assertIn("syncedAt", manifest)

    def test_sync_generated_files_copies_known_artifacts_and_images_and_writes_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source_dir = Path(tmp) / "generated"
            target_dir = Path(tmp) / "web" / "public" / "generated"
            source_dir.mkdir(parents=True)
            (source_dir / "images").mkdir()

            for filename in SYNC_FILENAMES:
                (source_dir / filename).write_text(
                    json.dumps({"name": filename}, ensure_ascii=False),
                    encoding="utf-8",
                )
            (source_dir / "images" / "sample.png").write_bytes(b"png-bytes")

            summary = sync_generated_files(
                source_dir=source_dir,
                target_dir=target_dir,
                title="상표심사기준",
            )

            self.assertEqual(summary["fileCount"], len(SYNC_FILENAMES))
            self.assertEqual(summary["imageFileCount"], 1)
            self.assertTrue((target_dir / "manifest.json").exists())
            self.assertTrue((target_dir / "document-data.json").exists())
            self.assertTrue((target_dir / "images" / "sample.png").exists())

    def test_sync_generated_files_replaces_stale_images_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source_dir = Path(tmp) / "generated"
            target_dir = Path(tmp) / "web" / "public" / "generated"
            source_dir.mkdir(parents=True)
            (source_dir / "images").mkdir()
            (target_dir / "images").mkdir(parents=True)

            for filename in SYNC_FILENAMES:
                (source_dir / filename).write_text(
                    json.dumps({"name": filename}, ensure_ascii=False),
                    encoding="utf-8",
                )

            (source_dir / "images" / "fresh.png").write_bytes(b"fresh")
            (target_dir / "images" / "stale.png").write_bytes(b"stale")

            sync_generated_files(
                source_dir=source_dir,
                target_dir=target_dir,
                title="상표심사기준",
            )

            self.assertTrue((target_dir / "images" / "fresh.png").exists())
            self.assertFalse((target_dir / "images" / "stale.png").exists())

    def test_sync_generated_files_fails_when_sources_are_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source_dir = Path(tmp) / "generated"
            target_dir = Path(tmp) / "web" / "public" / "generated"
            source_dir.mkdir(parents=True)

            with self.assertRaises(SystemExit):
                sync_generated_files(
                    source_dir=source_dir,
                    target_dir=target_dir,
                    title="상표심사기준",
                )


if __name__ == "__main__":
    unittest.main()
