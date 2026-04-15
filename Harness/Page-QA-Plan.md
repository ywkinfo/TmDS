# Page QA Plan

원본 PDF 개별 페이지와 웹앱 렌더 결과를 비교할 때 사용할 실행 계획이다.

핵심 원칙은 3단 비교다.

1. 원본 PDF 페이지 이미지: `data/generated/review-pages/*.jpg`
2. 추출 중간 산출물: `data/generated/page-review.json`
3. 최종 렌더 산출물: `web/public/generated/document-data.json`

## Risk Tiers

고위험 페이지는 전수 점검한다.

- `table/form` 페이지
- `search-index.json` 기준 같은 페이지에 2개 이상 entry가 겹치는 페이지
- `confidence="low"` 페이지
- `hasOverride=true` 페이지
- `mergeFirstGroupWithPreviousPage=true` 페이지

중위험 페이지는 표본 점검 후 결함률에 따라 확대한다.

- `list` 페이지 중 `【...】`, `< ... >`, `※ ...` 같은 특수 표제가 있는 페이지
- 부록/서식 페이지 중 표와 본문이 혼합된 페이지
- 최근 수정 패턴과 동일한 챕터 안의 페이지

저위험 페이지는 표본 점검한다.

- 순수 `prose` + `confidence="high"` 페이지
- `decorative/structural` 페이지
- 특수 표제가 없는 순수 `list` 페이지

## Source Queries

같은 페이지에 여러 section이 겹치는지 보려면 `page-review.json`만으로는 부족하다.
`search-index.json`의 `pageStart` / `pageEnd`를 페이지별로 펼쳐서 교차 분석해야 한다.

- `entryType != "search-alias"` 기준 page overlap을 계산한다.
- 동일 페이지에 2개 이상 entry가 존재하면 multi-section page로 분류한다.

현재 데이터 기준 참고 수치:

- 2개 entry 겹침: 50 페이지
- 3개 entry 겹침: 26 페이지
- 4개 entry 겹침: 3 페이지
- 합계: 79 페이지

## Automatic Flags

자동 flag는 아래 규칙으로 계산한다.

1. multi-section page
2. `confidence="low"`
3. `hasOverride=true`
4. `mergeFirstGroupWithPreviousPage=true`
5. `【...】` boxed heading 포함
6. `< ... >` angle heading 포함
7. `table/form` 페이지인데 대응 `table-crop` 이미지가 없음
8. `table-crops/`와 `reader-synthetic-table`이 같은 챕터에 동시에 존재
9. 본문 챕터에 `제`, `편`, 숫자 단독 문단 잔존

`review-pages/`는 모든 페이지의 원본 QA 이미지가 항상 존재하므로 flag 기준으로 쓰지 않는다.
표 검증은 반드시 `table-crops/` 존재 여부를 기준으로 본다.

## Audit Output

페이지 QA 산출물은 `data/generated/page-audit-report.json`으로 저장한다.

각 페이지 레코드에 최소한 다음 필드를 포함한다.

- `pageNumber`
- `pageLabel`
- `chapterSlug`
- `sectionId`
- `pageLayoutKind`
- `confidence`
- `hasOverride`
- `mergeFirstGroupWithPreviousPage`
- `riskTier`
- `sectionOverlapCount`
- `flags`

## Execution Order

1. `npm run web:prepare`
2. `npm run qa:page-audit`
3. `npm run test:python`
4. `npm run web:test`

부분 수정일 때는 아래 단축 루프를 사용한다.

- content 조립 로직 수정:
  - `npm run content:build`
  - `npm run qa:prepare`
  - `npm run web:sync`
- review layout 수정:
  - `npm run qa:prepare`
  - `npm run web:sync`
- 스타일 수정:
  - `npm run web:test`

## Review Workflow

고위험 페이지는 전수 검토한다.

- 표 페이지는 table-crop bbox가 표 끝까지 포함하는지
- 같은 페이지 다중 절은 앞뒤 절이 섞이지 않았는지
- boxed / angle heading은 독립 단락인지
- merge-first-group 페이지는 이전 페이지 마지막 문단과 자연스럽게 이어지는지

중위험 페이지는 표본 검토 후 확대한다.

- 우선순위는 `list + special heading`
- 결함률이 높으면 챕터 전체로 확장한다.

저위험 페이지는 챕터당 2~3페이지 표본만 확인한다.

## Fix Strategy

문제는 항상 페이지 단위가 아니라 패턴 단위로 수정한다.

- same-page section bleed
- boxed / angle heading merge
- running header fragment leak
- table crop miss
- table continuation miss

generated JSON은 손으로 고치지 않는다.
파서, 분류기, crop 규칙, paragraph override를 수정하고 재생성한다.
