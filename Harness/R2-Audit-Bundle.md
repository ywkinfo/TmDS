# R2 Audit Bundle

`audit:r2-bundle`는 기존 `data/generated/` QA 산출물을 읽어 오프라인 연구용 R2 bundle을 만든다.

## 목적

- source of truth는 항상 `data/generated/`
- 파생 산출물은 `data/research/pdf-web-audit/<bundle-id>/` 아래에만 기록
- 기존 baseline bundle과 `web/public/generated/` sync 동작은 건드리지 않음
- 브라우저/수동 검증은 생성하지 않고 `ledger.md`에 manual-only로 명시

## 입력

- `data/generated/pdf-inventory.json`
- `data/generated/page-review.json`
- `data/generated/page-audit-report.json`
- `data/generated/search-index.json`
- `data/generated/document-data.json`

## 출력

- `page-coverage-ledger.json`
- `special-sections.json`
- `regression-diff.json`
- `search-corpus.json`
- `search-results.json`
- `search-checks.json`
- `content-fidelity-diff.json`
- `ledger.md`

## 실행

기본 실행은 오늘 날짜 기준 `<today>-r2` bundle id를 사용한다.

```bash
npm run audit:r2-bundle
```

명시적으로 bundle id를 고정하려면 Python module entrypoint를 직접 사용한다.

```bash
python -m pipeline.build_r2_audit_bundle --bundle-id 2026-04-18-r2
```

`--bundle-id`가 `-r2`로 끝나면 같은 날짜의 baseline bundle(`-r2` 제거)을 자동으로 regression 비교 대상으로 읽는다.

## 설계 메모

- `inventory`는 `pageNumber`, `pageLabel`, `pageKind`, `hasText`, `imageCount`, `topLines`를 제공한다.
- `page-review`는 `pageLayoutKind`, `confidence`, `hasOverride`, `mergeFirstGroupWithPreviousPage`, `chapterSlug`, `sectionId`를 제공한다.
- `page-audit-report`는 `riskTier`, `flags`, `sectionOverlapCount`를 제공한다.
- `search-index`는 `entryType`, `pageStart`, `pageEnd`, `pageLabelStart`, `pageLabelEnd`, `chapterSlug`, `sectionId`를 제공한다.
- `document-data`는 `slug`를 사용하므로 generator 내부에서만 `chapterSlug`와 normalize 한다.
- `search-checks.json`은 고정 query set(`머리말`, `일러두기`, `부 록`, `부칙`, `별첨`, `개정 연혁`, `지리적 표시`, `FTA`, `재검토기한`)에 대한 offline expected runtime route 요약이다. raw top match 자체는 `search-results.json`에 남긴다.
- `content-fidelity-diff.json`은 truthful first pass 비교 산출물이다. PDF 쪽은 `page-review[].paragraphs[].text`를 재조합한 텍스트를, rendered 쪽은 같은 페이지와 겹치는 non-`search-alias` `search-index` 엔트리 텍스트를 사용한다.
- 이 비교는 page-exact HTML 추출이나 브라우저 렌더 비교가 아니다. `document-data.html`은 chapter/section marker 존재 여부를 보는 coarse evidence로만 쓴다.
- 따라서 `content-fidelity-diff.json.comparisonStatus`가 `candidate-backed`여도 “정확한 PDF↔HTML 1:1 page mapping”을 의미하지 않는다. 이 값은 single-candidate coarse comparison이 가능했다는 뜻일 뿐이다. `ambiguous`와 `unsupported`를 적극적으로 남겨 한계를 드러내는 것이 계약이다.
