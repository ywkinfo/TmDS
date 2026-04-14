from __future__ import annotations

from pipeline.common import detect_page_label, parse_page_label_line


def test_parse_page_label_line_supports_roman_and_arabic() -> None:
    assert parse_page_label_line("- i -") == "i"
    assert parse_page_label_line("- xxii -") == "xxii"
    assert parse_page_label_line("- 972 -") == "972"


def test_detect_page_label_ignores_non_label_lines() -> None:
    assert detect_page_label(["2024", "심판편람", "제14판"]) is None
    assert detect_page_label(["제1편 특허심판 일반", "- 1 -", "제1장 의의"]) == "1"


def test_detect_page_label_allows_label_after_fragmented_heading_lines() -> None:
    assert detect_page_label(["제", "1", "편", "제1장 의의", "- 3 -", "제1편 특허심판 일반"]) == "3"
