# V2_SPRING

V2_SPRING은 자율 소프트웨어 스튜디오를 **클린룸 방식으로 다시 구축**한
프로젝트입니다.

이 저장소는 이전 Paperclip V1 구현의 연장이 아닙니다. 아래 항목들에 대한
새로운 단일 진실 원천으로 취급합니다.

- 컨트롤 플레인
- 영속 원장
- 플래너 / 리플래너 계약
- 실행 워크포스 계약
- 창업자가 검증 가능한 run 루프

## 방향성

V2_SPRING은 다음과 같은 시스템으로 구축되고 있습니다.

**상태 기반, 원장 기반, planner/executor 분리, 사람 거버넌스 중심의 자율 소프트웨어 스튜디오**

핵심 스택 방향:
- 영속 기록 저장소는 Postgres
- 조정과 보조 통신은 Redis
- 계획/재계획은 LangGraph
- 실행 크루는 CrewAI

첫 번째 마일스톤은 완성형 UI가 아닙니다.  
첫 번째 마일스톤은 **CLI에서 검증 가능한 tracer bullet**입니다.

## 이 저장소에 들어 있는 것

- `docs/` - 차터, ADR, 아키텍처, 검증 스펙, 런북
- `infra/` - 로컬 인프라와 기초 부트스트랩
- `src/v2_spring/` - 핵심 Python 패키지
- `apps/` - 나중에 붙일 founder/operator 표면
- `archive/v1/` - 보존용 V1 참고 문서와 초기 골격 산출물

## 현재 우선순위

1. 차터와 경계 확정
2. 핵심 상태 모델
3. 결정론적 substrate
4. CLI tracer bullet

## 빠른 시작

```bash
make env-local
make infra-up
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
make db-upgrade
v2-spring doctor
v2-spring --help
```

## 환경 프로필

- 로컬 호스트 개발: `make env-local`
- Docker 네트워크 내부 앱 프로세스: `make env-docker`
- VM / 단일 호스트 배포: `make env-vm`

환경 변수 계약과 설명:
- [환경 변수 문서](docs/runbooks/ENVIRONMENT_VARIABLES.md)

## 주요 문서

- [최종 방향성](docs/charter/FINAL_DIRECTION.md)
- [실행 계획](docs/architecture/EXECUTION_PLAN.md)
- [환경 변수 문서](docs/runbooks/ENVIRONMENT_VARIABLES.md)
- [Founder 검증 요구사항](docs/verification/FOUNDER_VERIFICATION_REQUIREMENTS.md)
- [Tracer bullet](docs/specs/TRACER_BULLET.md)
- [ADR 인덱스](docs/adr/README.md)
