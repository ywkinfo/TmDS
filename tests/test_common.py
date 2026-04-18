from __future__ import annotations

from pipeline.common import (
    make_excerpt,
    merge_extracted_text_segments,
    normalize_search_text,
    repair_extracted_text_spacing,
    strip_running_header_lines,
)


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


def test_repair_extracted_text_spacing_fixes_known_broken_compounds() -> None:
    text = (
        "청구인 또 는 피 청구인이 심 판 절차에 의 하여 국선대리 인을 선임하고 "
        "그 결과를 말 한다."
    )

    assert repair_extracted_text_spacing(text) == (
        "청구인 또는 피청구인이 심판절차에 의하여 국선대리인을 선임하고 "
        "그 결과를 말한다."
    )


def test_repair_extracted_text_spacing_preserves_normal_particle_spacing() -> None:
    assert repair_extracted_text_spacing("처분은 법률에 의하여 효력이 발생한다.") == (
        "처분은 법률에 의하여 효력이 발생한다."
    )


def test_merge_extracted_text_segments_repairs_line_boundary_breaks() -> None:
    assert merge_extracted_text_segments(
        "이러한 특별행정심판제도를 일반 행정 심판· 소송과 달리 별도로 두고 있는 이유는 산업재",
        "산권은 전문적인 기술내용 등을 바탕으로 준사법적인 절차를 거쳐 처리되기 때문이다.",
    ) == (
        "이러한 특별행정심판제도를 일반 행정심판· 소송과 달리 별도로 두고 있는 이유는 "
        "산업재산권은 전문적인 기술내용 등을 바탕으로 준사법적인 절차를 거쳐 처리되기 때문이다."
    )
    assert merge_extracted_text_segments(
        "상대방ㆍ제3자가 가진 것으",
        "로서 제출의무가 있는 문서는 그 소지인에 대한 제출명령을 신청하는 방법에 의한다.",
    ) == "상대방ㆍ제3자가 가진 것으로서 제출의무가 있는 문서는 그 소지인에 대한 제출명령을 신청하는 방법에 의한다."
    assert merge_extracted_text_segments(
        "심판장은 위 신청에 대하여 문서소지",
        "자에게 관련문서 사본․등본의 문서제출명령을 한다.",
    ) == "심판장은 위 신청에 대하여 문서소지자에게 관련문서 사본․등본의 문서제출명령을 한다."
    assert merge_extracted_text_segments(
        "문서를 가진 사람, 증명할 사실 등을 기재하여 신청하도록 하여야 한다(특허심판 증거조사 사",
        "무규정§31①).",
    ) == "문서를 가진 사람, 증명할 사실 등을 기재하여 신청하도록 하여야 한다(특허심판 증거조사 사무규정§31①)."
    assert merge_extracted_text_segments(
        "문서송부촉탁은 위 ③의 경우이며, 심판장은 제3자에게 문서의 송부를 촉탁할 수 있다(민소",
        "§29413)). 심판장은 당사자가 특허심판원으로 하여금 문서제출의무를 부담하는 문서소지자에 대해 문서제출을 요구하도록 한다.",
    ) == "문서송부촉탁은 위 ③의 경우이며, 심판장은 제3자에게 문서의 송부를 촉탁할 수 있다(민소§29413)). 심판장은 당사자가 특허심판원으로 하여금 문서제출의무를 부담하는 문서소지자에 대해 문서제출을 요구하도록 한다."


def test_normalize_search_text_repairs_broken_terms_across_newlines() -> None:
    assert normalize_search_text("기간을 말\n\n한다.\n\n심판장 또\n\n는 심사관") == "기간을 말한다. 심판장 또는 심사관"


def test_make_excerpt_repairs_broken_terms_before_truncation() -> None:
    assert make_excerpt("등록특허를 신속히 재검토하여 하자가 있는 특\n\n허를 조기에 시정한다.", limit=80) == (
        "등록특허를 신속히 재검토하여 하자가 있는 특허를 조기에 시정한다."
    )
