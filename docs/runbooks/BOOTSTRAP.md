# 부트스트랩 런북

1. `.env.example`을 기준으로 `.env`를 만듭니다
2. `make infra-up`으로 Postgres와 Redis를 시작합니다
3. Python 가상환경을 만듭니다
4. `pip install -e .`로 로컬 패키지를 설치합니다
5. CLI 엔트리포인트를 실행해 저장소가 정상 부팅되는지 확인합니다
6. UI 작업에 들어가기 전에 tracer bullet 구현을 먼저 시작합니다
