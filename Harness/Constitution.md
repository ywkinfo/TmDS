# 심사기준 Harness Constitution

이 문서는 이 워크스페이스에서 agent 종류와 무관하게 유지할 영구 원칙을 정리합니다.
현재 phase와 성공 기준은 `PROJECT-OVERVIEW.md`, 실제 실행 계약은 `README.md`를 기준으로 확인합니다.

## Core Principles

1. 원문 추적 가능성이 편의보다 우선입니다.
   구조화 결과는 항상 원본 PDF 페이지와 다시 연결될 수 있어야 합니다.
2. 누락 없는 추출이 보기 좋은 출력보다 우선입니다.
   예쁜 HTML보다 inventory와 coverage가 먼저 맞아야 합니다.
3. generated 산출물은 파이프라인의 결과물입니다.
   출력이 틀리면 JSON을 손으로 고치지 말고 스크립트와 입력 규칙을 수정합니다.
4. 독립 워크스페이스 원칙을 유지합니다.
   이 폴더는 PDF 기반 하네스를 중심에 두고, 그 결과를 소비할 웹앱 레일을 명시적으로 분리한 구조로 운영합니다.
5. 구조 수치는 계약입니다.
   페이지 수, 부/장/항 수, 보충기준 수 같은 기준선은 QA에서 계속 확인합니다.

## Working Rules

- 판단 전에는 먼저 원본 PDF와 생성 스크립트 결과를 확인합니다.
- page code, 목차, 이미지 개수처럼 재현 가능한 사실을 우선 기록합니다.
- 라이선스, 공개 범위, 이미지 재사용 허용 여부는 기술 구조와 별개로 메모에 남깁니다.
- 불확실한 구조는 추정으로 덮지 말고 `coverage-report.json`에 남깁니다.
- 구현 agent는 `PLAN.md`보다 `README.md`, `Harness/*.md`, `data/source/source-config.json`, 실제 파이프라인 스크립트를 현재 계약으로 우선 해석합니다.

## Decision Order

1. 이 문서의 영구 원칙
2. `PROJECT-OVERVIEW.md`
3. `Harness/Style-Guide.md`
4. `Harness/Architecture.md`
5. `Harness/Content-Spec.md`
6. 실제 스크립트와 생성 결과
