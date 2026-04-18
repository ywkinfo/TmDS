# 심판편람 제14판 Harness

심판편람 제14판 PDF를 구조화된 JSON과 정적 웹 리더로 변환하는 하네스입니다.
이 워크스페이스는 PDF inventory, PDF 북마크 outline, reader TOC, chapter HTML, search index,
exploration index, inline image asset을 재현 가능한 방식으로 생성하는 것을 목표로 합니다.

## Structure

- `data/source/심판편람 제14판.pdf`: 원본 PDF
- `data/source/source-config.json`: 입력과 구조 기준선
- `data/research/`: 수동 보정 메모, 성능 측정 메모, QA 기록
- `data/generated/`: 파이프라인 산출물
- `data/notebooklm/`: NotebookLM 업로드용 Markdown 산출물
- `pipeline/`: Python 파이프라인
- `tests/`: Python 테스트
- `web/`: generated JSON을 읽는 React/Vite 리더
- `Harness/`: 작업 원칙, 구조 계약, QA 게이트

## Commands

- `npm run content:inventory`: 페이지 inventory 생성
- `npm run content:outline`: PDF 북마크 outline 추출
- `npm run content:toc`: reader TOC 생성
- `npm run content:images`: inline image asset 추출
- `npm run content:build`: document-data, search-index, exploration-index 생성
- `npm run content:qa`: 구조 및 coverage QA
- `npm run content:prepare`: 전체 content pipeline 실행
- `npm run content:notebooklm`: `content:prepare` 실행 후 NotebookLM용 Markdown(`data/notebooklm/parts/*.md`, `data/notebooklm/chapters/*.md`) 생성
- `npm run audit:r2-bundle`: `data/generated/`를 source of truth로 사용해 `data/research/pdf-web-audit/<today>-r2/` 오프라인 R2 audit bundle(`page-coverage-ledger`, `special-sections`, `search-checks`, truthful first-pass `content-fidelity-diff` 등) 생성
- `npm run web:sync`: generated JSON과 image asset을 `web/public/generated/`로 동기화
- `npm run web:prepare`: content pipeline 실행 후 웹 리더 산출물 동기화
- `npm run web:dev`: 개발 서버 실행
- `npm run web:build`: 정적 리더 빌드
- `npm run test`: Python + web 테스트 실행

## Deployment

- GitHub Pages는 `.github/workflows/deploy-pages.yml`로 `main` push마다 자동 배포됩니다.
- 현재 구조에서는 `web/public/generated/`에 커밋된 reader asset을 기준으로 `web/dist/`를 빌드해 배포합니다.
- 공개 URL은 기본적으로 `https://ywkinfo.github.io/TmDS/`입니다.

## Notes

- PDF 원본은 직접 수정하지 않습니다.
- 공개 저장소에는 원본 PDF를 포함하지 않습니다. 현재 공개본은 `web/public/generated/`의 reader asset을 기준으로 동작합니다.
- generated JSON과 image asset은 손으로 수정하지 않고 스크립트 재실행으로 갱신합니다.
- `outline.json`, `pdf-inventory.json`, `coverage-report.json`, `image-manifest.json`은 하네스 진단용이며 웹으로는 직접 sync하지 않습니다.
- `pageStart`/`pageEnd`는 PDF 페이지 번호이고, `pageLabelStart`/`pageLabelEnd`는 사용자에게 보여줄 인쇄 페이지 번호입니다.
