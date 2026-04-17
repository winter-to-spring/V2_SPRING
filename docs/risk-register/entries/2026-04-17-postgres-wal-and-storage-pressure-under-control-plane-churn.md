# Risk ID: RISK-0060
Title: heartbeat와 audit churn 아래에서 WAL 및 storage pressure가 급격히 증가할 수 있음
Class: Before Scale
Status: Open
Owner: Storage / Operations
Observed In: Step 22 contention-soak planning

## 설명

contention이 통제되더라도, 잦은 renewal과 촘촘한 audit/event write는 많은
양의 Postgres WAL과 disk churn을 만들 수 있습니다.

이 문제는 replayability와 세밀한 운영 증거를 중요하게 여기는 control plane에서
특히 중요합니다.

## 영향

- 디스크 사용량이 예상보다 빠르게 증가할 수 있음
- backup / replication 동작이 악화될 수 있음
- 앱 자체가 맞더라도 운영 복구가 더 어려워질 수 있음

## 왜 중요한가

V2_SPRING은 control-plane correctness를 storage layer에 지속 불가능한
write churn으로 몰아넣는 방식으로 해결해서는 안 됩니다.

## 권장 완화책

- heartbeat hygiene와 thresholded renewal을 유지한다
- worker fanout을 넓히기 전에 WAL/storage pressure를 관측한다
- scale 전에 대용량 audit 데이터의 retention / archival policy를 정의한다
- storage churn을 놀랄 일이 아니라 1급 운영 지표로 다룬다

## Capability Gate
- Capability: sustained multi-worker Postgres operations
- Gate mode: Before Scale
- Blocked until: write churn and storage pressure are understood well enough for operational planning

## Issue Link
- GitHub Issue: #49

## Doc Links
- ADR:
- Design note: ../../issues/STEP_22_POSTGRES_CONTENTION_AND_CONTROLLER_DB_BOUNDARY.md

## 종료 기준

- 대표적인 churn 아래에서 WAL/storage 증가 패턴이 측정된다
- 더 넓은 rollout 전에 retention 또는 archive 기준이 존재한다

## Last Updated
- 2026-04-17
