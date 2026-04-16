# Page QA Plan

원본 PDF 개별 페이지와 웹앱 렌더 결과를 비교할 때 사용할 실행 계획이다.

핵심 원칙은 3단 비교 + queue 기반 운영이다.

1. 원본 PDF 페이지 이미지: `data/generated/review-pages/*.jpg`
2. 추출 중간 산출물: `data/generated/page-review.json`
3. 최종 렌더 산출물: `data/generated/document-data.json`, `data/generated/search-index.json`

수동 검수는 항상 두 화면을 함께 본다.

- 추출 QA: `/qa/page/:pageNumber` + `page-review.json` + `review-pages/*.jpg`
- 최종 렌더 QA: `chapterPath`가 가리키는 reader route + `document-data.json`

`QAPage.tsx`는 추출 디버거다. 최종 HTML 자체를 보여주지 않는다.
따라서 페이지 검수는 `/qa/page/N`만 보고 끝내지 않고, 반드시 대응하는 chapter route를 같이 확인한다.

## Risk Tiers

고위험 페이지는 queue로 전수 관리한다.

- `table/form` 페이지
- `confidence="low"` 페이지
- `hasOverride=true` 페이지
- `search-index.json` overlap 기준 multi-section page
- `mergeFirstGroupWithPreviousPage=true` 페이지

중위험 페이지는 flag 기반으로 점검한다.

- `list` 페이지 중 `【...】`, `< ... >`, `※ ...` 같은 특수 표제가 있는 페이지
- `toc` 페이지
- prose/list/toc에서 `제`, `편`, 숫자 단독 문단이 남은 페이지

저위험 페이지는 샘플링한다.

- 플래그 없는 `list` 페이지
- 기본 `decorative/structural` 페이지
- 순수 `prose` + `confidence="high"` 페이지

주의:

- `decorative/structural`은 기본적으로 저위험이지만 `low-confidence`, `hasOverride`, `multi-section-page`, `page-merge`가 겹치면 고위험으로 승격한다.
- `list` 페이지는 수가 많으므로 전수 검토하지 않는다. queue에 오른 페이지와 플래그 기반 샘플만 본다.

## Source Queries

같은 페이지에 여러 section이 겹치는지 보려면 `page-review.json`만으로는 부족하다.
`search-index.json`의 `pageStart` / `pageEnd`를 페이지별로 펼쳐서 교차 분석해야 한다.

- `entryType != "search-alias"` 기준으로 page overlap을 계산한다.
- page별 unique key는 `"{entryType}::{sectionId}"`로 잡는다.
- 동일 페이지에 2개 이상 entry가 존재하면 multi-section page로 분류한다.

`page-review.json`의 `chapterSlug` / `sectionId`는 `qa_prepare.resolve_page_locator()`가 고른 대표 locator 하나다.
페이지가 실제로 여러 section에 걸쳐 있는지 판단하는 근거로 쓰지 않는다.

표 검증도 `review-pages/*.jpg` 존재 여부로 판단하지 않는다.
`review-pages`는 모든 페이지에 대해 항상 생성되는 full-page QA 이미지다.
표 검증은 반드시 최종 렌더 HTML 안의 `table-crops/{page}-*` 참조 여부와 실제 렌더 결과를 기준으로 본다.

## Automatic Flags

자동 flag는 아래 규칙으로 계산한다.

1. `multi-section-page`
   - `search-index.json` overlap 기준
   - `entryType="search-alias"` 제외
2. `low-confidence`
   - `page-review.json`의 `confidence="low"`
3. `has-override`
   - `page-review.json`의 `hasOverride=true`
4. `page-merge`
   - `page-review.json`의 `mergeFirstGroupWithPreviousPage=true`
5. `boxed-heading`
   - `【...】`, `[ ... ]` 류 단락
6. `angle-heading`
   - `< ... >` 류 단락
7. `missing-table-crop`
   - `table/form` 페이지인데 해당 페이지의 rendered HTML 구간에 `table-crops/{page}-*` 참조가 없음
8. `synthetic-table-remains`
   - 문제 페이지가 속한 rendered 구간에 `reader-synthetic-table`이 잔존함
9. `structural-fragment-paragraph`
   - prose/list/toc에서 `제`, `편`, 숫자 단독 문단이 잔존함

주의:

- `review-pages/`는 crop 성공 여부의 근거가 아니다.
- `structural-fragment-paragraph`는 `decorative/structural` 페이지에서 노이즈가 될 수 있으므로 기본 downweight 대상으로 본다.

## Audit Output

QA 산출물은 아래 4개를 함께 본다.

1. `data/generated/page-audit-report.json`
   - 페이지별 risk tier와 flags의 기준 산출물
2. `data/generated/page-review-queue.json`
   - 고위험 페이지의 우선순위 queue
3. `data/generated/page-review-batches.json`
   - 상위 queue를 10페이지 단위 소배치로 나눈 작업용 산출물
4. `data/generated/page-review.json`
   - 페이지 단위 추출 디버깅 산출물

운영 기준은 다음과 같다.

- `page-audit-report.json`은 분석 기준 산출물이다.
- `page-review-queue.json`과 `page-review-batches.json`이 실제 검수 우선순위의 source of truth다.
- `QAPage.tsx` 내부 flagged navigation은 현재 `confidence="low"`와 `hasOverride=true`만 잡으므로 전체 high-risk review driver로 사용하지 않는다.

`page-audit-report.json`의 페이지 레코드는 최소한 다음 필드를 포함한다.

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

queue / batch 산출물은 여기에 아래 필드를 추가로 사용한다.

- `priorityScore`
- `queueLane`
- `qaPath`
- `chapterPath`

## Execution Order

전체 검증 루프는 아래 순서로 고정한다.

1. `npm run web:prepare`
2. `npm run qa:prepare`
3. `npm run qa:page-audit`
4. `npm run qa:review-queue`
5. `npm run qa:review-batches`
6. `npm run test:python`
7. `npm run web:test`

중요:

- `web:prepare`는 `content:prepare + web:sync`만 수행한다.
- `web:prepare` 안에 `qa:prepare`는 포함되지 않는다.
- `page-review.json`이 갱신되면 `page-audit-report.json`, `page-review-queue.json`, `page-review-batches.json`은 stale 상태가 되므로 반드시 다시 생성한다.

부분 수정일 때는 아래 단축 루프를 사용한다.

- inventory / outline / toc / image asset까지 바뀐 경우:
  - `npm run web:prepare`
  - `npm run qa:prepare`
  - `npm run qa:page-audit`
  - `npm run qa:review-queue`
  - `npm run qa:review-batches`
- `review_layout.py`, `build_content.py`, `paragraph-overrides.json` 같이 page review와 content assembly를 함께 바꾸는 경우:
  - `npm run content:build`
  - `npm run web:sync`
  - `npm run qa:prepare`
  - `npm run qa:page-audit`
  - `npm run qa:review-queue`
  - `npm run qa:review-batches`
- audit / queue / batch 규칙만 바꾸는 경우:
  - `npm run qa:page-audit`
  - `npm run qa:review-queue`
  - `npm run qa:review-batches`
- web QA 화면만 바꾸는 경우:
  - `npm run web:test`

## Review Workflow

검수는 직접 페이지 목록을 손으로 만들지 않는다.
항상 `page-review-queue.json`에서 시작하고, 실제 작업 단위는 `page-review-batches.json`을 기준으로 잡는다.

1. `page-review-batches.json`의 Batch A부터 시작한다.
2. 각 페이지는 `qaPath`와 `chapterPath`를 쌍으로 연다.
3. 추출 QA와 최종 렌더 QA를 분리해서 판단한다.
4. 같은 패턴이 반복되면 페이지별 수동 수정이 아니라 패턴 수정으로 전환한다.
5. 수정 후에는 batch 전체를 다시 확인하고, queue를 재생성해 우선순위 변화를 본다.

페이지 유형별 확인 포인트:

- 표 페이지:
  - `/qa/page/N`에서 bbox와 문단 분해가 표 끝까지 맞는지
  - 최종 렌더에서 해당 페이지용 `table-crop` 이미지가 들어갔는지
  - synthetic table이 남아 있지 않은지
- multi-section 페이지:
  - `search-index.json` overlap 기준으로 인접 section이 섞이지 않았는지
  - 최종 렌더에서 heading / body 경계가 올바른지
- page-merge 페이지:
  - 항상 `(N-1, N)` 페어로 확인한다.
  - 이전 페이지 마지막 문단과 현재 페이지 첫 문단이 한 번만 자연스럽게 이어지는지 본다.
- boxed / angle heading 페이지:
  - 독립 단락으로 남아야 하는지
  - 본문과 잘못 합쳐지지 않았는지

중위험 페이지는 고위험 batch 처리 후 본다.

- 우선순위는 `list + special heading`
- `toc`는 별도 샘플링 대상으로 두되, 전체를 전수 검토하지 않는다.

저위험 페이지는 챕터당 2~3페이지 샘플만 확인한다.

## Fix Strategy

문제는 항상 페이지 단위가 아니라 패턴 단위로 수정한다.

- same-page section bleed
- boxed / angle heading merge
- running header fragment leak
- table crop miss
- table continuation miss
- page merge false positive / false negative

generated JSON은 손으로 고치지 않는다.
파서, 분류기, crop 규칙, paragraph override를 수정하고 재생성한다.

성공 기준은 단순히 “페이지가 queue에서 사라졌는가”만이 아니다.

- queue에서 빠졌는지
- 더 낮은 risk tier로 내려갔는지
- 남아 있더라도 flag 이유가 설명 가능하고 의도와 일치하는지

queue를 줄이는 것보다 잘못된 confidence와 잘못된 렌더를 줄이는 것을 우선한다.
