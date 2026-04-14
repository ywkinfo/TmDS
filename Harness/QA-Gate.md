# 심사기준 Harness QA Gate

작업 완료 직전에 확인하는 최소 게이트입니다.

## Always

- [ ] `npm run content:prepare` 통과
- [ ] `data/generated/pdf-inventory.json` 생성
- [ ] `data/generated/toc.json` 생성
- [ ] `data/generated/document-data.json` 생성
- [ ] `data/generated/search-index.json` 생성
- [ ] `data/generated/exploration-index.json` 생성
- [ ] `data/generated/coverage-report.json` 생성

## Structure Contract

- [ ] inventory의 `pageCount`가 575와 일치
- [ ] toc의 `partCount`가 10과 일치
- [ ] toc의 `chapterCount`가 85와 일치
- [ ] toc의 `itemCount`가 319과 일치
- [ ] toc의 `supplementCount`가 2와 일치
- [ ] `document-data.json`의 `chapterCount`가 85와 일치
- [ ] `search-index.json`이 비어 있지 않음

## Coverage Contract

- [ ] `coverage-report.json`의 `missingPageCodes`가 비어 있음
- [ ] `coverage-report.json`의 `unmappedChapterCount`가 0
- [ ] `coverage-report.json`의 `unmappedSectionCount`가 0
- [ ] `document-data.json`, `search-index.json`, `exploration-index.json`의 `pageStart`가 `toc.meta.tocPages`를 직접 가리키지 않음
- [ ] chapter summary/html, search excerpt/text, exploration excerpt가 `목 차`류 선두 텍스트로 시작하지 않음

메모:

- count mismatch가 생기면 generated를 손으로 수정하지 말고 파서나 source config를 수정합니다.
- 라이선스 검토와 공개 가능성 평가는 별도 트랙이며, 이 게이트는 구조 복원 하네스 자체만 검증합니다.
