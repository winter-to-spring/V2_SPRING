# Gemini Cross-Check Workflow

## Purpose

Direct Gemini execution from the Codex environment does not share your local
Gemini authentication session. Because of that, the practical review loop is:

1. Run Gemini locally on your machine.
2. Paste the Gemini review output back into this thread.
3. Let Codex classify, confirm, and apply the fixes.

## Recommended review modes

### 1. Scaffold review

Use this after changing infrastructure or project setup files.

```bash
bin/gemini-review scaffold
```

Target files:

- `docker-compose.yml`
- `.env.example`
- `pyproject.toml`
- `README.md`

### 2. Workflow review

Use this after changing the LangGraph flow or state model.

```bash
bin/gemini-review workflow
```

Target files:

- `src/agent_studio/state.py`
- `src/agent_studio/graph.py`
- `src/agent_studio/main.py`
- `docs/V1_WORKFLOW.md`

### 3. Infra review

Use this after changing database or bootstrap structure.

```bash
bin/gemini-review infra
```

Target files:

- `docker-compose.yml`
- `config/postgres/init/001_init.sql`
- `README.md`
- `.env.example`

## How to use the output

Ask Gemini for findings only. Then bring the output here and I will:

- separate real findings from noise
- classify severity
- decide what should change now vs later
- apply the actual code or config edits

## Review standard

The review prompt is intentionally opinionated:

- prioritize bugs, risks, missing pieces, and operational issues
- avoid generic praise
- keep findings concrete
- focus on v1 practicality

