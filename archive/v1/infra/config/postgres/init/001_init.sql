CREATE TABLE IF NOT EXISTS projects (
    project_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS workflow_runs (
    run_id TEXT PRIMARY KEY,
    project_id TEXT REFERENCES projects(project_id),
    request_id TEXT NOT NULL,
    goal TEXT NOT NULL,
    current_phase TEXT NOT NULL,
    current_owner TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'in_progress',
    blocker TEXT NOT NULL DEFAULT '',
    lint TEXT NOT NULL DEFAULT 'unknown',
    typecheck TEXT NOT NULL DEFAULT 'unknown',
    unit_test TEXT NOT NULL DEFAULT 'unknown',
    module_smoke TEXT NOT NULL DEFAULT 'unknown',
    requirements_approved BOOLEAN NOT NULL DEFAULT FALSE,
    release_approved BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS run_steps (
    step_id BIGSERIAL PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES workflow_runs(run_id) ON DELETE CASCADE,
    node_name TEXT NOT NULL,
    status TEXT NOT NULL,
    notes TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS approvals (
    approval_id BIGSERIAL PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES workflow_runs(run_id) ON DELETE CASCADE,
    approval_type TEXT NOT NULL,
    decision TEXT NOT NULL DEFAULT 'pending',
    reviewer TEXT NOT NULL DEFAULT '',
    decided_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS artifacts (
    artifact_id BIGSERIAL PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES workflow_runs(run_id) ON DELETE CASCADE,
    artifact_type TEXT NOT NULL,
    path TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_workflow_runs_project_id
    ON workflow_runs(project_id);

CREATE INDEX IF NOT EXISTS idx_run_steps_run_id
    ON run_steps(run_id);

CREATE INDEX IF NOT EXISTS idx_approvals_run_id
    ON approvals(run_id);

CREATE INDEX IF NOT EXISTS idx_artifacts_run_id
    ON artifacts(run_id);

