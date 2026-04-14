from __future__ import annotations

from pipeline.common import strip_running_header_lines


def test_strip_running_header_lines_removes_known_boilerplate_and_fragmented_part_markers() -> None:
    lines = [
        "제",
        "1",
        "편",
        "제1장 의의",
        "- 3 -",
        "제1편 특허심판 일반",
        "제1장 의의",
        "2024 심판편람 제14판",
        "Intellectual Property Trial and",
        "Appeal Board",
        "특허심판이란 특허· 실용신안· 디자인· 상표 출원에 대하여",
    ]

    assert strip_running_header_lines(lines) == [
        "- 3 -",
        "제1편 특허심판 일반",
        "제1장 의의",
        "특허심판이란 특허· 실용신안· 디자인· 상표 출원에 대하여",
    ]
