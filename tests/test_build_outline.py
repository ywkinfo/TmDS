from __future__ import annotations

from pathlib import Path

from pipeline import build_inventory
from pipeline.build_outline import collect_outline_entries
from pipeline.common import load_config, load_generated_json, open_pdf


def test_collect_outline_entries_matches_pdf_baseline() -> None:
    inventory_path = Path(__file__).resolve().parents[1] / "data" / "generated" / "pdf-inventory.json"
    if not inventory_path.exists():
        build_inventory.main()

    config = load_config()
    document = open_pdf(config)
    inventory = load_generated_json("pdf-inventory.json")
    label_by_page = {
        int(page["pageNumber"]): page.get("pageLabel")
        for page in inventory.get("pages", [])
    }
    entries = collect_outline_entries(document, label_by_page)

    assert len(entries) == 491
    assert sum(1 for entry in entries if entry["level"] == 1) == 4
    assert sum(1 for entry in entries if entry["level"] == 2) == 32
    assert sum(1 for entry in entries if entry["level"] == 3) == 203
    assert sum(1 for entry in entries if entry["level"] == 4) == 252
