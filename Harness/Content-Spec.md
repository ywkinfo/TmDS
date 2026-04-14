# TmDS Harness Content Spec

## Canonical Inputs

- 원본 PDF: `data/source/심판편람 제14판.pdf`
- 입력 설정: `data/source/source-config.json`

## Inventory Rules

- 각 페이지는 `pageNumber`, `pageLabel`, `pageKind`, `charCount`, `imageCount`, `hasText`, `topLines`를 가진다.
- `pageKind`는 `frontmatter`, `body`, `unlabeled` 3종으로 유지한다.
- `pageLabel`은 `- i -`, `- xxii -`, `- 32 -` 같은 상단 라벨만 canonical로 인정한다.
- 로마 숫자 라벨은 gap이 있어도 허용한다.

## Outline Rules

- PDF 북마크는 `pymupdf.Document.get_toc()` 결과를 canonical로 사용한다.
- Level-2는 `part`, Level-3는 `chapter`, Level-4는 `section`으로 매핑한다.
- `제14-1편`, `제14-2편`, `제15-1편`, `제15-2편`은 독립 `part`로 취급한다.

## Reader Rules

- `part/chapter/section`의 시작 페이지는 outline 기준이다.
- 표시용 인쇄 페이지 번호는 inventory에서 복원한 `pageLabel`을 사용한다.
- `목차` 페이지는 search/exploration/document 본문에 직접 노출하지 않는다.
- `categories`는 1차 구현에서 비워 둘 수 있고, 이후 제목 패턴 분석으로 보강한다.
