# TmDS Project Overview

## Current Goal

심판편람 제14판 PDF를 재현 가능한 하네스로 구조화하고, `TmEG`와 유사한 정적 웹 리더에서 읽을 수 있게 만든다.

## Current Phase

1. PDF inventory, outline, TOC, image extraction, content build, QA 파이프라인 정착
2. generated JSON을 읽는 phase-1 reader shell 연결
3. 첫 green run 기준선과 성능 메모 정리

## Definition Of Done

- `npm run content:prepare` 통과
- `npm run web:build` 통과
- `npm run test` 통과
- 구조 기준선 `pageCount=1381`, `level2Count=32`, `level3Count=203`, `level4Count=252`, `outlineCount=491` 검증
