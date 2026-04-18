from __future__ import annotations

import json

from pipeline.build_r2_audit_bundle import (
    build_bundle_artifacts,
    build_content_fidelity_diff,
    build_page_coverage_ledger,
    search_corpus_entries,
    write_bundle,
)


def make_sample_sources() -> tuple[dict, list[dict], dict, list[dict], dict]:
    inventory = {
        "pages": [
            {
                "pageNumber": 1,
                "pageLabel": None,
                "pageKind": "body",
                "hasText": True,
                "imageCount": 0,
                "topLines": ["머리말"],
            },
            {
                "pageNumber": 2,
                "pageLabel": "i",
                "pageKind": "frontmatter",
                "hasText": True,
                "imageCount": 0,
                "topLines": ["목차"],
            },
            {
                "pageNumber": 3,
                "pageLabel": "1",
                "pageKind": "body",
                "hasText": True,
                "imageCount": 1,
                "topLines": ["제1편 특허심판 일반"],
            },
            {
                "pageNumber": 4,
                "pageLabel": "2",
                "pageKind": "body",
                "hasText": True,
                "imageCount": 0,
                "topLines": ["개정내용"],
            },
            {
                "pageNumber": 5,
                "pageLabel": "3",
                "pageKind": "body",
                "hasText": True,
                "imageCount": 0,
                "topLines": ["공공기 관 설명하 게"],
            },
            {
                "pageNumber": 6,
                "pageLabel": "4",
                "pageKind": "body",
                "hasText": True,
                "imageCount": 0,
                "topLines": ["후보 표본 페이지"],
            },
        ]
    }
    page_review = [
        {
            "pageNumber": 1,
            "chapterSlug": "front-preface",
            "sectionId": "overview",
            "pageLayoutKind": "prose",
            "confidence": "high",
            "hasOverride": False,
            "mergeFirstGroupWithPreviousPage": False,
            "paragraphs": [{"text": "머리말 본문"}],
        },
        {
            "pageNumber": 2,
            "chapterSlug": None,
            "sectionId": None,
            "pageLayoutKind": "toc",
            "confidence": "medium",
            "hasOverride": False,
            "mergeFirstGroupWithPreviousPage": False,
            "paragraphs": [{"text": "목차"}],
        },
        {
            "pageNumber": 3,
            "chapterSlug": "chapter-a",
            "sectionId": "part-intro",
            "pageLayoutKind": "prose",
            "confidence": "low",
            "hasOverride": False,
            "mergeFirstGroupWithPreviousPage": False,
            "paragraphs": [{"text": "제1편 특허심판 일반 지리적 표시 안내"}],
        },
        {
            "pageNumber": 4,
            "chapterSlug": "appendix-history",
            "sectionId": "overview",
            "pageLayoutKind": "prose",
            "confidence": "low",
            "hasOverride": False,
            "mergeFirstGroupWithPreviousPage": True,
            "paragraphs": [{"text": "개정 연혁 2021년 개정내용"}],
        },
        {
            "pageNumber": 5,
            "chapterSlug": "chapter-b",
            "sectionId": "overview",
            "pageLayoutKind": "prose",
            "confidence": "low",
            "hasOverride": False,
            "mergeFirstGroupWithPreviousPage": False,
            "paragraphs": [{"text": "공공기 관 설명하 게"}],
        },
        {
            "pageNumber": 6,
            "chapterSlug": "chapter-c",
            "sectionId": "overview",
            "pageLayoutKind": "prose",
            "confidence": "low",
            "hasOverride": False,
            "mergeFirstGroupWithPreviousPage": False,
            "paragraphs": [{"text": "후보 표본 페이지 본문"}],
        },
    ]
    page_audit = {
        "pages": [
            {"pageNumber": 1, "riskTier": "low", "flags": [], "sectionOverlapCount": 1},
            {"pageNumber": 2, "riskTier": "medium", "flags": [], "sectionOverlapCount": 0},
            {"pageNumber": 3, "riskTier": "high", "flags": ["low-confidence"], "sectionOverlapCount": 1},
            {"pageNumber": 4, "riskTier": "high", "flags": ["page-merge", "boxed-heading"], "sectionOverlapCount": 1},
            {"pageNumber": 5, "riskTier": "medium", "flags": ["korean-linebreak-residue"], "sectionOverlapCount": 1},
            {"pageNumber": 6, "riskTier": "high", "flags": ["low-confidence"], "sectionOverlapCount": 1},
        ]
    }
    search_index = [
        {
            "id": "front-preface-overview",
            "chapterSlug": "front-preface",
            "chapterTitle": "머리말",
            "sectionId": "overview",
            "sectionTitle": "개요",
            "entryType": "overview",
            "partTitle": "전면부",
            "pageStart": 1,
            "pageEnd": 1,
            "pageLabelStart": None,
            "pageLabelEnd": None,
            "text": "머리말 본문",
            "excerpt": "머리말",
        },
        {
            "id": "chapter-a-part-intro",
            "chapterSlug": "chapter-a",
            "chapterTitle": "제1장 의의",
            "sectionId": "part-intro",
            "sectionTitle": "제1편 특허심판 일반",
            "entryType": "part-intro",
            "partTitle": "제1편 특허심판 일반",
            "pageStart": 3,
            "pageEnd": 3,
            "pageLabelStart": "1",
            "pageLabelEnd": "1",
            "text": "제1편 특허심판 일반",
            "excerpt": "제1편 특허심판 일반",
        },
        {
            "id": "appendix-revision-history-alias",
            "chapterSlug": "appendix-history",
            "chapterTitle": "2. 2021년 개정내용",
            "sectionId": "part-intro",
            "sectionTitle": "개정 연혁",
            "entryType": "search-alias",
            "partTitle": "부 록",
            "pageStart": 4,
            "pageEnd": 4,
            "pageLabelStart": "2",
            "pageLabelEnd": "2",
            "text": "개정 연혁 2021년 개정내용",
            "excerpt": "개정 연혁",
        },
        {
            "id": "appendix-overview",
            "chapterSlug": "appendix-history",
            "chapterTitle": "2. 2021년 개정내용",
            "sectionId": "overview",
            "sectionTitle": "개요",
            "entryType": "overview",
            "partTitle": "부 록",
            "pageStart": 4,
            "pageEnd": 4,
            "pageLabelStart": "2",
            "pageLabelEnd": "2",
            "text": "2021년 개정내용",
            "excerpt": "2021년 개정내용",
        },
        {
            "id": "fta-gi-overview",
            "chapterSlug": "chapter-a",
            "chapterTitle": "지리적 표시 단체표장",
            "sectionId": "overview",
            "sectionTitle": "지리적 표시",
            "entryType": "item",
            "partTitle": "제1편 특허심판 일반",
            "pageStart": 3,
            "pageEnd": 3,
            "pageLabelStart": "1",
            "pageLabelEnd": "1",
            "text": "지리적 표시 안내",
            "excerpt": "지리적 표시",
        },
        {
            "id": "chapter-b-overview",
            "chapterSlug": "chapter-b",
            "chapterTitle": "제2장 설명",
            "sectionId": "overview",
            "sectionTitle": "개요",
            "entryType": "overview",
            "partTitle": "제1편 특허심판 일반",
            "pageStart": 5,
            "pageEnd": 5,
            "pageLabelStart": "3",
            "pageLabelEnd": "3",
            "text": "공공기관 설명하게",
            "excerpt": "공공기관 설명하게",
        },
        {
            "id": "chapter-c-overview",
            "chapterSlug": "chapter-c",
            "chapterTitle": "제3장 표본",
            "sectionId": "overview",
            "sectionTitle": "개요",
            "entryType": "overview",
            "partTitle": "제1편 특허심판 일반",
            "pageStart": 6,
            "pageEnd": 6,
            "pageLabelStart": "4",
            "pageLabelEnd": "4",
            "text": "후보 표본 페이지 본문",
            "excerpt": "후보 표본 페이지 본문",
        },
    ]
    document_data = {
        "chapters": [
            {
                "slug": "front-preface",
                "title": "머리말",
                "partTitle": "전면부",
                "pageStart": 1,
                "pageEnd": 1,
                "html": '<section id="overview"></section>',
            },
            {
                "slug": "chapter-a",
                "title": "제1장 의의",
                "partTitle": "제1편 특허심판 일반",
                "pageStart": 4,
                "pageEnd": 4,
                "html": '<section id="overview"></section><section id="part-intro"></section>',
            },
            {
                "slug": "appendix-history",
                "title": "2. 2021년 개정내용",
                "partTitle": "부 록",
                "pageStart": 4,
                "pageEnd": 4,
                "html": '<section id="overview"></section>',
            },
            {
                "slug": "chapter-b",
                "title": "제2장 설명",
                "partTitle": "제1편 특허심판 일반",
                "pageStart": 5,
                "pageEnd": 5,
                "html": '<section id="overview"></section>',
            },
            {
                "slug": "chapter-c",
                "title": "제3장 표본",
                "partTitle": "제1편 특허심판 일반",
                "pageStart": 6,
                "pageEnd": 6,
                "html": '<section id="overview"></section>',
            },
        ]
    }
    return inventory, page_review, page_audit, search_index, document_data


def test_build_page_coverage_ledger_classifies_delivery_modes_and_normalizes_chapter_fields() -> None:
    inventory, page_review, page_audit, search_index, document_data = make_sample_sources()

    ledger = build_page_coverage_ledger(
        inventory=inventory,
        page_review=page_review,
        page_audit=page_audit,
        search_index=search_index,
        document_data=document_data,
    )

    assert ledger["summary"]["deliveryModeCounts"] == {
        "reader-body": 4,
        "toc-transform": 1,
        "search-only": 1,
    }
    assert ledger["summary"]["tocSpan"] == [2, 2]
    assert ledger["pages"][2]["deliveryMode"] == "search-only"
    assert ledger["pages"][2]["searchEntries"][0]["chapterSlug"] == "chapter-a"
    assert ledger["pages"][3]["chapterMatches"] == [
        {"slug": "chapter-a", "title": "제1장 의의"},
        {"slug": "appendix-history", "title": "2. 2021년 개정내용"},
    ]


def test_search_corpus_entries_ranks_exact_section_match_before_text_only_match() -> None:
    corpus_entries = [
        {
            "chapterSlug": "chapter-a",
            "chapterTitle": "제1장 의의",
            "sectionId": "part-intro",
            "sectionTitle": "개정 연혁",
            "entryType": "search-alias",
            "partTitle": "부 록",
            "pageStart": 2,
            "pageEnd": 2,
            "route": "#/chapter/chapter-a/part-intro",
            "text": "개정 연혁 안내",
        },
        {
            "chapterSlug": "chapter-b",
            "chapterTitle": "부록 개요",
            "sectionId": "overview",
            "sectionTitle": "개요",
            "entryType": "overview",
            "partTitle": "부 록",
            "pageStart": 1,
            "pageEnd": 1,
            "route": "#/chapter/chapter-b/overview",
            "text": "본문에 개정 연혁이 포함된다",
        },
    ]

    matches = search_corpus_entries("개정 연혁", corpus_entries)

    assert [match["chapterSlug"] for match in matches] == ["chapter-a", "chapter-b"]
    assert matches[0]["score"] > matches[1]["score"]


def test_build_content_fidelity_diff_selects_required_pages_and_reports_limitations() -> None:
    inventory, page_review, page_audit, search_index, document_data = make_sample_sources()

    page_coverage_ledger = build_page_coverage_ledger(
        inventory=inventory,
        page_review=page_review,
        page_audit=page_audit,
        search_index=search_index,
        document_data=document_data,
    )
    fidelity_diff = build_content_fidelity_diff(
        page_coverage_ledger=page_coverage_ledger,
        page_review=page_review,
        page_audit=page_audit,
        search_index=search_index,
        document_data=document_data,
    )

    compared_pages = {page["pageNumber"]: page for page in fidelity_diff["pages"]}
    assert fidelity_diff["sampling"]["residuePages"]["includedPageNumbers"] == [5]
    assert fidelity_diff["sampling"]["highRiskProseSample"]["includedPageNumbers"] == [4, 6]
    assert "page-merge" not in fidelity_diff["sampling"]["highRiskProseSample"]["exclusions"]
    assert compared_pages[4]["comparisonStatus"] == "ambiguous"
    assert any("page-merge" in limitation for limitation in compared_pages[4]["limitations"])
    assert compared_pages[6]["comparisonStatus"] == "candidate-backed"
    assert compared_pages[6]["coarseRenderEvidence"]["chapterFound"] is True
    assert compared_pages[6]["coarseRenderEvidence"]["sectionMarkerFound"] is True
    assert len(compared_pages[6]["candidateEntries"]) == 1
    assert compared_pages[5]["comparisonStatus"] == "candidate-backed"
    assert compared_pages[5]["tokenCounts"]["missingTokenCount"] > 0
    assert compared_pages[5]["limitations"][0].startswith("PDF-side text comes from repaired page-review paragraphs")
    assert fidelity_diff["summary"]["sampledHighRiskPageCount"] == 2
    assert fidelity_diff["summary"]["residuePageCount"] == 1


def test_build_bundle_artifacts_and_write_bundle_outputs_expected_files(tmp_path) -> None:
    inventory, page_review, page_audit, search_index, document_data = make_sample_sources()
    baseline_artifacts = {
        "page-coverage-ledger.json": {
            "summary": {
                "pageCount": 6,
                "deliveryModeCounts": {"reader-body": 4, "toc-transform": 1, "search-only": 1},
                "textPageCount": 6,
                "uncoveredBodyPages": [],
                "uncoveredBodyPageCount": 0,
                "textPagesNotExposed": [],
                "textPagesTocTransform": [2],
                "nullLabelTextPages": [1],
                "tocSpan": [2, 2],
            }
        },
        "special-sections.json": {
            "front_preface": [],
            "front_notes": [],
            "toc": [],
            "part_intro": [],
            "revision_history": [],
            "legend": [],
            "appendix": [],
            "reconsideration_deadline": [],
            "fta_gi": [],
        },
    }

    artifacts = build_bundle_artifacts(
        bundle_id="2026-04-18-r2",
        inventory=inventory,
        page_review=page_review,
        page_audit=page_audit,
        search_index=search_index,
        document_data=document_data,
        baseline_artifacts=baseline_artifacts,
        baseline_bundle_id="2026-04-18",
    )

    written_paths = write_bundle(tmp_path, artifacts)
    assert {path.name for path in written_paths} == {
        "page-coverage-ledger.json",
        "special-sections.json",
        "content-fidelity-diff.json",
        "regression-diff.json",
        "search-corpus.json",
        "search-results.json",
        "search-checks.json",
        "ledger.md",
    }

    special_sections = json.loads((tmp_path / "special-sections.json").read_text(encoding="utf-8"))
    content_fidelity_diff = json.loads((tmp_path / "content-fidelity-diff.json").read_text(encoding="utf-8"))
    search_results = json.loads((tmp_path / "search-results.json").read_text(encoding="utf-8"))
    search_checks = json.loads((tmp_path / "search-checks.json").read_text(encoding="utf-8"))
    regression_diff = json.loads((tmp_path / "regression-diff.json").read_text(encoding="utf-8"))
    ledger_text = (tmp_path / "ledger.md").read_text(encoding="utf-8")

    assert any(record.get("sectionTitle") == "개정 연혁" for record in special_sections["revision_history"])
    assert content_fidelity_diff["summary"]["comparedPageCount"] == 3
    assert any(result["query"] == "머리말" for result in search_results["results"])
    assert any(record.get("matchedTerm") == "지리적 표시" for record in special_sections["fta_gi"])
    assert any(check["query"] == "머리말" and check["route"] == "#/chapter/front-preface" for check in search_checks)
    assert any(
        check["query"] == "개정 연혁" and check["route"] == "#/chapter/appendix-history/part-intro"
        for check in search_checks
    )
    assert any(check["query"] == "FTA" and check["result"] == "empty" for check in search_checks)
    assert regression_diff["artifacts"]["page-coverage-ledger.json"]["status"] == "unchanged"
    assert regression_diff["artifacts"]["special-sections.json"]["status"] == "changed"
    assert "content-fidelity-diff.json" in ledger_text
    assert "manual/browser evidence" in ledger_text
