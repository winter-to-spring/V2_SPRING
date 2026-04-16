# Bootstrap Runbook

1. Create `.env` from `.env.example`
2. Start Postgres and Redis with `make infra-up`
3. Create a Python virtual environment
4. Install the local package with `pip install -e .`
5. Run the CLI entrypoint and confirm the repo boots
6. Begin implementing the tracer bullet before any UI work
