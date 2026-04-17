# ADR-0005: Founder 검증 표면

## 상태

Accepted

## 배경

V1은 시스템이 "돌아간다"고 말할 수는 있었지만, founder가 실제로 무슨 일이
일어났는지 독립적으로 검증할 수는 없었습니다.

## 결정

Founder verification은 핵심 아키텍처 요구사항입니다. 시스템은 입력, 과정,
결정, artifact, approval, outcome을 replay 가능한 형태로 노출해야 합니다.
그 첫 증거는 UI가 아니라 CLI입니다.

Founder/operator progress surface는 추가로 아래 규칙을 따릅니다.

- progress surface는 별도로 쓰는 summary table이 아니라 **on-the-fly projection**
  이어야 합니다
- founder-facing 기본 표면은 compact summary입니다
- 기본 cockpit을 오염시키지 않으면서 디버깅할 수 있도록 명시적인 `raw` /
  `trace` escape hatch가 존재해야 합니다
- founder-facing JSON 출력은 typed read model 위에 있어야 하며, 그래야 이후 UI나
  자동화가 같은 계약을 재사용할 수 있습니다
- founder interaction ergonomics는 짧은 enum + text 명령을 기본으로 하고,
  multiline 입력을 위한 file-based escape hatch를 제공해야 합니다

## 결과

- replay 가능한 event history는 필수입니다.
- artifact와 decision 저장은 선택 사항이 아닙니다.
- founder-facing UI는 CLI에서 검증 가능한 증거가 생긴 뒤에 옵니다.
- founder/operator progress view는 같은 ledger-backed 상태로부터 파생되기 때문에
  replay와 일관성을 유지해야 합니다.
