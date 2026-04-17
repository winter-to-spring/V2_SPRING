# 아키텍처 개요

V2_SPRING은 네 개의 계층으로 구성됩니다.

1. **Ledger and Governance**
   - 영속 엔티티
   - 승인
   - 예산
   - 리스크

2. **Deterministic Substrate**
   - Postgres
   - Redis
   - queue와 lease semantics
   - 결정론적 executor

3. **Autonomous Cognition**
   - LangGraph planner / replanner
   - action proposal과 선택

4. **Execution Workforce**
   - CrewAI 전문 실행 풀
   - builder
   - QA
   - integrator

사람 검증은 이 네 계층 위에 놓이며, 반드시 저장된 증거로 뒷받침되어야
합니다.
