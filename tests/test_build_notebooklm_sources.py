from __future__ import annotations

import json
import tempfile
from pathlib import Path

from pipeline.build_notebooklm_sources import export_notebooklm_sources


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def test_export_notebooklm_sources_supports_custom_generated_dir_and_policy_rules() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        generated_dir = Path(tmp) / "generated"
        output_dir = Path(tmp) / "notebooklm"
        generated_dir.mkdir(parents=True)

        document_data = {
            "meta": {"title": "테스트 문서"},
            "chapters": [
                {
                    "id": "front-preface",
                    "slug": "front-preface",
                    "title": "머리말",
                    "summary": "머리말",
                    "html": '<section id="overview"><h2>머리말</h2><p>전면부 본문</p><figure class="reader-figure"><img src="./generated/images/x.png" alt="머리말 이미지" loading="lazy" /></figure></section>',
                    "hasImage": True,
                    "imageCount": 1,
                    "headings": [],
                    "partTitle": "전면부",
                    "pageLabel": None,
                    "pageStart": 1,
                    "pageEnd": 1,
                    "pageLabelStart": None,
                    "pageLabelEnd": None,
                },
                {
                    "id": "chapter-a",
                    "slug": "chapter-a",
                    "title": "제1장 테스트",
                    "summary": "테스트 장",
                    "html": (
                        '<section id="overview"><h2>제1장 테스트</h2><p>개요 문단</p></section>'
                        '<section id="part-intro"><h3>제1편 테스트</h3><p>이 편은 다음 장으로 구성됩니다.</p></section>'
                        '<section id="제1절-본문"><h3>제1절 본문</h3><p>제외될 문단</p></section>'
                    ),
                    "hasImage": False,
                    "imageCount": 0,
                    "headings": [{"id": "제1절-본문", "depth": 3, "title": "제1절 본문"}],
                    "partTitle": "제1편 테스트",
                    "pageLabel": "1",
                    "pageStart": 10,
                    "pageEnd": 11,
                    "pageLabelStart": "1",
                    "pageLabelEnd": "2",
                },
                {
                    "id": "chapter-b",
                    "slug": "chapter-b",
                    "title": "제2장 전체 제외",
                    "summary": "제외 장",
                    "html": '<section id="overview"><h2>제2장 전체 제외</h2><p>고위험 문단</p></section>',
                    "hasImage": False,
                    "imageCount": 0,
                    "headings": [],
                    "partTitle": "제1편 테스트",
                    "pageLabel": "3",
                    "pageStart": 12,
                    "pageEnd": 12,
                    "pageLabelStart": "3",
                    "pageLabelEnd": "3",
                },
                {
                    "id": "appendix",
                    "slug": "appendix",
                    "title": "1. 부록 장",
                    "summary": "부록",
                    "html": '<section id="overview"><h2>1. 부록 장</h2><p>부록 본문</p></section>',
                    "hasImage": False,
                    "imageCount": 0,
                    "headings": [],
                    "partTitle": "부 록",
                    "pageLabel": "A-1",
                    "pageStart": 100,
                    "pageEnd": 100,
                    "pageLabelStart": "A-1",
                    "pageLabelEnd": "A-1",
                },
            ],
        }
        review_queue = {
            "summary": {},
            "queue": [
                {
                    "pageNumber": 11,
                    "pageLabel": "2",
                    "chapterSlug": "chapter-a",
                    "sectionId": "제1절-본문",
                    "pageLayoutKind": "prose",
                    "confidence": "high",
                    "hasOverride": False,
                    "mergeFirstGroupWithPreviousPage": False,
                    "sectionOverlapCount": 1,
                    "riskTier": "high",
                    "flags": ["page-merge"],
                    "flagSummary": "page-merge",
                    "priorityScore": 99,
                    "queueLane": "accuracy-critical",
                    "qaPath": "/qa/page/11",
                    "chapterPath": "/chapter/chapter-a/제1절-본문",
                    "priorityRank": 1,
                },
                {
                    "pageNumber": 12,
                    "pageLabel": "3",
                    "chapterSlug": "chapter-b",
                    "sectionId": "overview",
                    "pageLayoutKind": "prose",
                    "confidence": "high",
                    "hasOverride": False,
                    "mergeFirstGroupWithPreviousPage": False,
                    "sectionOverlapCount": 0,
                    "riskTier": "high",
                    "flags": ["low-confidence"],
                    "flagSummary": "low-confidence",
                    "priorityScore": 88,
                    "queueLane": "accuracy-critical",
                    "qaPath": "/qa/page/12",
                    "chapterPath": "/chapter/chapter-b/overview",
                    "priorityRank": 2,
                },
            ],
        }

        _write_json(generated_dir / "document-data.json", document_data)
        _write_json(generated_dir / "page-review-queue.json", review_queue)

        summary = export_notebooklm_sources(
            generated_dir=generated_dir,
            output_dir=output_dir,
            title="테스트 문서",
        )

        assert summary["partFileCount"] == 2
        assert summary["chapterFileCount"] == 2
        assert summary["excludedChapterCount"] == 2
        assert summary["omittedSectionCount"] == 1

        chapter_files = sorted((output_dir / "chapters").glob("*.md"))
        assert [path.name for path in chapter_files] == [
            "001__front-preface.md",
            "002__chapter-a.md",
        ]

        chapter_a_text = (output_dir / "chapters" / "002__chapter-a.md").read_text(encoding="utf-8")
        assert "이 편은 다음 장으로 구성됩니다." not in chapter_a_text
        assert "제외될 문단" not in chapter_a_text
        assert "생략: 제1절 본문 section은 고위험 페이지 검토 항목 때문에" in chapter_a_text
        assert "<section" not in chapter_a_text

        front_preface_text = (output_dir / "chapters" / "001__front-preface.md").read_text(encoding="utf-8")
        assert "[이미지 생략: 머리말 이미지]" in front_preface_text

        excluded_text = (output_dir / "excluded.md").read_text(encoding="utf-8")
        assert "제2장 전체 제외" in excluded_text
        assert "section heading이 없어 chapter 전체를 NotebookLM v1에서 제외" in excluded_text
        assert "1. 부록 장" in excluded_text
        assert "부록은 표/서식 의존도가 높아 NotebookLM v1에서 제외" in excluded_text


def test_export_notebooklm_sources_matches_current_dataset_shape() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        output_dir = Path(tmp) / "notebooklm"
        summary = export_notebooklm_sources(output_dir=output_dir, title="심판편람 제14판")

        part_files = sorted((output_dir / "parts").glob("*.md"))
        chapter_files = sorted((output_dir / "chapters").glob("*.md"))

        assert summary["partFileCount"] == 32
        assert len(part_files) == 32
        assert summary["chapterFileCount"] == 146
        assert len(chapter_files) == 146
        assert summary["maxPartWordCount"] < 500_000

        front_notes = next(path for path in chapter_files if path.name.endswith("__front-notes.md"))
        front_notes_text = front_notes.read_text(encoding="utf-8")
        assert "[이미지 생략: 일러두기]" in front_notes_text
        assert "<section" not in front_notes_text
        assert "<img" not in front_notes_text

        omitted_chapter = next(
            path
            for path in chapter_files
            if path.name.endswith("__제2장-심판청구서-접수-후-절차-심판정책과.md")
        )
        omitted_text = omitted_chapter.read_text(encoding="utf-8")
        assert "제7절 심판관지정 변경 통지서의 작성 및 통지 section은 고위험 페이지 검토 항목 때문에" in omitted_text
        assert "심판번호 및 심판관지정의 결재가 있으면" not in omitted_text

        excluded_text = (output_dir / "excluded.md").read_text(encoding="utf-8")
        assert "표지 및 발간정보" in excluded_text
        assert "1. 심판관계서식례 및 기재례" in excluded_text
        assert "제1장 의의" in excluded_text
        assert "section heading이 없어 chapter 전체를 NotebookLM v1에서 제외" in excluded_text

        part_with_multiple_chapters = next(
            path for path in part_files if path.name.endswith("__제2편-심판서류의-접수-심판관지정-및-열람.md")
        )
        part_text = part_with_multiple_chapters.read_text(encoding="utf-8")
        assert "\n---\n" in part_text
        assert "## 제외/생략" in part_text

        index_text = (output_dir / "index.md").read_text(encoding="utf-8")
        assert "- 업로드용 part 파일 수: 32" in index_text
        assert "- 검수용 chapter 파일 수: 146" in index_text
        assert "parts/" in index_text
