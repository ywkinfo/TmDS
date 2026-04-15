from __future__ import annotations

from pipeline.build_toc import build_outline_ranges, build_reader_parts, build_synthetic_parts


def test_build_reader_parts_keeps_split_parts_as_independent_parts() -> None:
    ranged_entries = build_outline_ranges(
        [
            {"index": 1, "level": 2, "title": "제14편 권리범위 확인심판", "pageStart": 557, "pageLabelStart": "529"},
            {
                "index": 2,
                "level": 3,
                "title": "제1장 권리범위 확인심판의 청구",
                "pageStart": 559,
                "pageLabelStart": "531",
                "parentIndex": 1,
            },
            {"index": 3, "level": 2, "title": "제14-1편 디자인권의 권리범위 확인심판", "pageStart": 601, "pageLabelStart": "573"},
            {
                "index": 4,
                "level": 3,
                "title": "제1장 개요",
                "pageStart": 603,
                "pageLabelStart": "575",
                "parentIndex": 3,
            },
        ],
        1381,
    )

    parts = build_reader_parts(ranged_entries, slug_max_length=80)

    assert len(parts) == 2
    assert parts[0]["fullTitle"] == "제14편 권리범위 확인심판"
    assert parts[1]["fullTitle"] == "제14-1편 디자인권의 권리범위 확인심판"


def test_build_synthetic_parts_keeps_front_notes_out_of_toc_pages() -> None:
    parts = build_synthetic_parts(
        page_count=1381,
        toc_pages=[11, 12],
        level1_entries={
            "일러두기": {
                "pageStart": 7,
                "pageEnd": 12,
                "pageLabelStart": "i",
                "pageLabelEnd": "vi",
            }
        },
    )

    front_notes = next(
        chapter
        for part in parts
        for chapter in part["chapters"]
        if chapter["id"] == "front-notes"
    )

    assert front_notes["pageStart"] == 7
    assert front_notes["pageEnd"] == 10
