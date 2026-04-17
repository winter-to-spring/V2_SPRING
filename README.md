# V2_SPRING

V2_SPRING is a clean-room rebuild of the autonomous software studio.

This repository is intentionally not a continuation of the previous Paperclip
V1 implementation. It is the new source of truth for:

- the control plane
- the durable ledger
- the planner and replanner contracts
- the execution workforce contracts
- the founder-verifiable run loop

## Direction

V2_SPRING is being built as a:

**state-driven, ledger-backed, planner/executor-separated, human-governed autonomous software studio**

Core stack direction:
- Postgres for durable records
- Redis for coordination
- LangGraph for planning and replanning
- CrewAI for execution crews

The first milestone is not a full UI.
The first milestone is a **CLI-verifiable tracer bullet**.

## What Lives Here

- `docs/` - charter, ADRs, architecture, verification specs, runbooks
- `infra/` - local infrastructure and substrate bootstrap
- `src/v2_spring/` - core Python package
- `apps/` - founder/operator surfaces later
- `archive/v1/` - preserved V1 reference materials and earlier skeleton artifacts

## Current Priority

1. Charter and boundaries
2. Core state model
3. Deterministic substrate
4. CLI tracer bullet

## Quick Start

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

## Environment Profiles

- local host development: `make env-local`
- Docker-networked app process: `make env-docker`
- VM / single-host deployment: `make env-vm`

Environment contract and variable reference:
- [Environment variables](docs/runbooks/ENVIRONMENT_VARIABLES.md)

## Key Documents

- [Final direction](docs/charter/FINAL_DIRECTION.md)
- [Execution plan](docs/architecture/EXECUTION_PLAN.md)
- [Environment variables](docs/runbooks/ENVIRONMENT_VARIABLES.md)
- [Founder verification requirements](docs/verification/FOUNDER_VERIFICATION_REQUIREMENTS.md)
- [Tracer bullet](docs/specs/TRACER_BULLET.md)
- [ADR index](docs/adr/README.md)
