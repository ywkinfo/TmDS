# PDF ↔ Web Audit (2026-04-18, updated after mobile/search fixes)

## 1. 전체 판정

**PASS**

전 페이지 coverage는 generated 기준과 실제 브라우저 확인 모두에서 누락 없이 유지되었고, front matter, appendix, 후면부, 대표 위험 구간의 reader route와 검색 진입이 정상 동작했다. 모바일 375px 기준에서 문제가 되었던 wide crop image는 이제 page/body 자체를 깨뜨리지 않고 `reader-figure-scroll` 안에서 가로 스크롤되는 방식으로 수용되며, appendix 개정내용도 `개정 연혁` 검색으로 진입 가능해졌다. PDF와 픽셀 단위로 동일하지는 않지만, 현재 확인한 범위에서는 웹앱만으로 같은 정보와 관계를 무리 없이 읽을 수 있는 상태다.

## 2. 검증 개요

- 총 PDF 페이지 수: `1381`
- 웹앱 chapter coverage 범위: `reader-body 1298p`, `toc-transform 18p`, `search-only 65p`, `text-bearing not-exposed 0p`
- generated coverage 요약:
  - `coverage-report.json.pageCount = 1381`
  - `uncoveredBodyPageCount = 0`
  - `errors = []`
  - `page-coverage-ledger.json.textPagesNotExposed = []`
- 실제 브라우저 검증 범위:
  - 홈 / 검색 UI
  - `front-preface`, `front-notes`
  - representative prose/image page: `page 307`
  - representative wide figure/table-crop page: `page 461`, `page 539`
  - special section representative: `page 890`, `appendix-intro`, `editorial-board`
- 모바일 검증 수행 여부: `예, 375x812`
- 데스크톱 검증 수행 여부: `예, 1440x1200`

## 3. 이슈 Ledger

| PDF 페이지(또는 범위) | PDF 섹션명 | 웹앱 대응 위치(URL/검색/목차 진입점) | 상태 | 문제 유형 | 관찰 내용 | 사용자 영향 | 권장 수정 방식 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `1-10` | 전면부 (`표지 및 발간정보`, `머리말`, `일러두기`) | 홈, `#/chapter/front-preface`, `#/chapter/front-notes`, 검색 `머리말` | PASS | 접근성 | front matter direct route와 검색 진입이 정상 동작한다. | 사용자 접근 문제 없음 | - |
| `11-28` | PDF 목차 스프레드 | 홈 TOC UI | Intentional transform | 목차 변환 | PDF 목차 페이지는 개별 본문으로 렌더되지 않지만 홈의 live TOC가 동일한 탐색 기능을 대체한다. `text-bearing not-exposed`는 0이다. | 픽셀 동일성은 없지만 탐색 기능은 유지된다. | - |
| `279-295` | 제8장 문서제출신청 및 조사의 촉탁(사실조회) | `#/chapter/%EC%A0%9C8%EC%9E%A5-%EB%AC%B8%EC%84%9C%EC%A0%9C%EC%B6%9C%EC%8B%A0%EC%B2%AD-%EB%B0%8F-%EC%A1%B0%EC%82%AC%EC%9D%98-%EC%B4%89%ED%83%81%EC%82%AC%EC%8B%A4%EC%A1%B0%ED%9A%8C/overview` | PASS | 정확성 | `것으 로서`, `문서소지 자에게`, `(민소 / §294...)` 줄경계 문제가 정리된 상태를 재확인했다. | 본문 이해와 법조문 연결이 자연스럽다. | - |
| `430-454` | 제3장 심결분류 > 제3절 심결분류표 | `#/chapter/%EC%A0%9C3%EC%9E%A5-%EC%8B%AC%EA%B2%B0%EB%B6%84%EB%A5%98/%EC%A0%9C3%EC%A0%88-%EC%8B%AC%EA%B2%B0%EB%B6%84%EB%A5%98%ED%91%9C` | Intentional transform | wide figure/table-crop | 모바일에서 crop 이미지 자체는 넓지만 `body.scrollWidth=375`, `article.scrollWidth=349`로 page-level overflow 없이 `reader-figure-scroll` 내부에서 수용된다. | 사용자는 본문 전체가 깨지지 않은 상태에서 표 이미지를 가로 스크롤해 읽을 수 있다. | - |
| `502-513` | 제2장 기간의 계산 | `#/chapter/%EC%A0%9C2%EC%9E%A5-%EA%B8%B0%EA%B0%84%EC%9D%98-%EA%B3%84%EC%82%B0/%EC%A0%9C5%EC%A0%88-%EB%B6%80%EA%B0%80%EA%B8%B0%EA%B0%84%EC%9D%98-%EC%A7%80%EC%A0%95` | Intentional transform | wide figure/table-crop | `table-crops/0530-1`~`0536-3`는 모바일에서 wrapper 내부 가로 스크롤 구조로 바뀌었고, body/article overflow는 없다. | 읽기 방식은 PDF와 다르지만 정보 접근은 가능하다. | - |
| `1057-1344` | 부록 및 개정내용 묶음 | 홈 TOC, 검색 `부 록`, 검색 `개정 연혁`, `#/chapter/1-%EC%8B%AC%ED%8C%90%EA%B4%80%EA%B3%84%EC%84%9C%EC%8B%9D%EB%A1%80-%EB%B0%8F-%EA%B8%B0%EC%9E%AC%EB%A1%80/part-intro`, `#/chapter/10-2021-2023%EB%85%84-%EC%8B%9C%ED%96%89-%EC%82%B0%EC%97%85%EC%9E%AC%EC%82%B0%EA%B6%8C%EB%B2%95-%EA%B0%9C%EC%A0%95%EB%82%B4%EC%9A%A9` | PASS | 접근성 / 검색 | appendix는 TOC, direct route, exact title 검색, generic query `개정 연혁`으로 모두 접근 가능하다. 모바일에서도 page-level overflow는 없다. | appendix discoverability가 개선되었다. | - |
| `1373-1381` | 심판편람편찬위원 (후면부) | 홈 링크, `#/chapter/editorial-board/overview` | PASS | 접근성 | 후면부 direct route와 홈 링크가 모두 동작하고 모바일/데스크톱 overflow도 없다. | tail content 접근 가능 | - |
| `지리적 표시` | 제9장 지리적 표시 단체표장의 등록취소심판 | 검색 `지리적 표시` → `#/chapter/%EC%A0%9C9%EC%9E%A5-%EC%A7%80%EB%A6%AC%EC%A0%81-%ED%91%9C%EC%8B%9C-%EB%8B%A8%EC%B2%B4%ED%91%9C%EC%9E%A5%EC%9D%98-%EB%93%B1%EB%A1%9D%EC%B7%A8%EC%86%8C%EC%8B%AC%ED%8C%90%EC%83%81-119-8` | PASS | 검색 정확도 | 대표 검색어가 관련 장으로 정상 이동한다. | 검색 경로 유지 | - |

## 4. 증거

### 사용한 검색어
- `머리말`
- `부 록`
- `지리적 표시`
- `2021∼2023년 시행 산업재산권법 개정내용`
- `개정 연혁`
- `FTA`
- `재검토기한`

### 스크린샷 파일명
- `page-home-web-desktop.png`
- `page-home-web-mobile.png`
- `page-0005-web-desktop.png`
- `page-0005-web-mobile.png`
- `page-0461-web-desktop.png`
- `page-0461-web-mobile.png`
- `page-1087-web-desktop.png`
- `page-1373-web-desktop.png`
- `page-1373-web-mobile.png`
- `page-0005-pdf.png`
- `page-0011-pdf.png`
- `page-0307-pdf.png`
- `page-0460-pdf.png`
- `page-0530-pdf.png`
- `page-1089-pdf.png`
- `page-1373-pdf.png`

### 원본 PDF 기준 근거
- `coverage-report.json`: `uncoveredBodyPageCount = 0`
- `page-coverage-ledger.json`: `textPagesNotExposed = []`, `toc-transform = 11-28`
- `pdf-inventory.json`: `nullLabelTextPages = [1,3,5,1373,1374,1375,1376,1377,1378,1379,1381]`
- `page-review.json` / `document-data.json`: page 307 line-break residue fix 확인

### 웹앱에서 실제 확인한 경로 / 검색 결과
- `머리말` → `#/chapter/front-preface`
- `부 록` → `#/chapter/1-%EC%8B%AC%ED%8C%90%EA%B4%80%EA%B3%84%EC%84%9C%EC%8B%9D%EB%A1%80-%EB%B0%8F-%EA%B8%B0%EC%9E%AC%EB%A1%80/part-intro`
- `지리적 표시` → `#/chapter/%EC%A0%9C9%EC%9E%A5-%EC%A7%80%EB%A6%AC%EC%A0%81-%ED%91%9C%EC%8B%9C-%EB%8B%A8%EC%B2%B4%ED%91%9C%EC%9E%A5%EC%9D%98-%EB%93%B1%EB%A1%9D%EC%B7%A8%EC%86%8C%EC%8B%AC%ED%8C%90%EC%83%81-119-8`
- `2021∼2023년 시행 산업재산권법 개정내용` → `#/chapter/10-2021-2023%EB%85%84-%EC%8B%9C%ED%96%89-%EC%82%B0%EC%97%85%EC%9E%AC%EC%82%B0%EA%B6%8C%EB%B2%95-%EA%B0%9C%EC%A0%95%EB%82%B4%EC%9A%A9`
- `개정 연혁` → `#/chapter/1-%EC%8B%AC%ED%8C%90%EA%B4%80%EA%B3%84%EC%84%9C%EC%8B%9D%EB%A1%80-%EB%B0%8F-%EA%B8%B0%EC%9E%AC%EB%A1%80/part-intro`
- `FTA` → empty-card, no source-backed result 확인
- `재검토기한` → empty-card, no source-backed result 확인

### 관련 generated 파일 근거
- `data/generated/coverage-report.json`
- `data/generated/pdf-inventory.json`
- `data/generated/document-data.json`
- `data/generated/search-index.json`
- `data/generated/page-review.json`
- `data/generated/page-audit-report.json`
- `data/research/pdf-web-audit/2026-04-18/page-coverage-ledger.json`
- `data/research/pdf-web-audit/2026-04-18/browser-metrics.json`
- `data/research/pdf-web-audit/2026-04-18/browser-metrics-followup.json`
- `data/research/pdf-web-audit/2026-04-18/search-checks.json`

## 5. 최종 승인 게이트

- 전 페이지 커버리지: **PASS**
- front matter 접근 가능: **PASS**
- appendix/부칙/별첨 접근 가능: **PASS**
- 표 의미 보존: **PASS**
- 이미지/도해 가독성: **PASS**
- 검색 정확도: **PASS**
- 모바일 가시성: **PASS**
- 데스크톱 가시성: **PASS**
