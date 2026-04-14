# TmDS Harness Architecture

## Purpose

이 워크스페이스는 심판편람 제14판 PDF를 독립적인 structured reader dataset으로 변환하는 PDF 중심 하네스입니다.
핵심 목표는 page inventory, PDF 북마크 outline, reader TOC, chapter HTML, search index, exploration index를
재현 가능한 방식으로 생성하고 이를 웹앱 리더가 바로 읽을 수 있게 유지하는 것입니다.

## Source Of Truth

- 원본 PDF: `data/source/심판편람 제14판.pdf`
- 입력 설정: `data/source/source-config.json`
- 생성 산출물: `data/generated/*.json`
- 파이프라인 스크립트: `pipeline/*.py`
- 웹앱 소비 레일: `web/`

## Pipeline

1. `build_inventory.py`: 페이지 라벨, top lines, 이미지 수, page kind inventory 생성
2. `build_outline.py`: PDF 북마크 outline 추출
3. `build_toc.py`: outline을 spine으로 reader TOC 구성
4. `build_images.py`: 반복되지 않는 inline image asset 추출
5. `build_content.py`: chapter HTML, search/exploration index 생성
6. `qa_content.py`: 구조 수치, 범위, coverage, toc leakage 검증
7. `sync_web_generated.py`: 웹 리더용 generated JSON과 image asset 동기화

## Reader Model

- `pageStart`/`pageEnd`: PDF 페이지 번호
- `pageLabelStart`/`pageLabelEnd`: 인쇄 페이지 번호
- Level-2 북마크는 reader `part`로 사용
- Level-3 북마크는 reader `chapter`로 사용
- Level-4 북마크는 reader `section`으로 사용
- Level-1 북마크 `머리말`, `일러두기`, `심판편람편찬위원`은 synthetic reader part/chapter로 재배치
- Level-1 `목차`는 inventory/QA에 남기되 reader/search 본문에서는 제외
