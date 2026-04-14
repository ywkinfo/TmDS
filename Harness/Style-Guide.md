# 심사기준 Harness Style Guide

이 문서는 이 워크스페이스의 스크립트, JSON 산출물, 메모 파일에 공통 적용되는 기본 작성 규칙을 정리합니다.

## Python

- 표준 라이브러리와 현재 환경에서 이미 제공되는 모듈을 우선 사용합니다.
- 예외 메시지는 실패 원인이 바로 읽히도록 구체적으로 작성합니다.
- 경로, JSON 키, 데이터 구조는 사람이 grep하기 쉽게 명시적 이름을 사용합니다.
- 함수는 한 가지 책임만 가지게 유지합니다.

## JSON And Generated Data

- generated JSON은 항상 pretty-print와 trailing newline을 유지합니다.
- 구조 QA에서 읽는 핵심 키 이름을 자주 바꾸지 않습니다.
- `pageNumber`, `pageCode`, `partTitle`, `chapterTitle`, `sectionTitle`처럼 탐색에 직접 쓰이는 필드는 축약하지 않습니다.

## Content Extraction

- 원문 삭제보다 보수적 보존을 우선합니다.
- 추출이 애매한 경우 과도한 정제보다 원문 가까운 텍스트를 남깁니다.
- 검색 엔트리는 원문으로 다시 추적 가능한 locator를 함께 가져야 합니다.

## Verification

- 구조 계약 변경 시에는 `npm run content:prepare`를 다시 실행합니다.
- page count, toc count, 누락 page code는 자동 QA로 확인합니다.
- 수동 보정이 필요하면 generated가 아니라 source config나 보정 규칙 파일에서 처리합니다.
