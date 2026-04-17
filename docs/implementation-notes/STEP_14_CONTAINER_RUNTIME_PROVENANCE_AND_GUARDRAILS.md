# Step 14 - Container Runtime Provenance And Guardrails

## What Changed

Step 14 hardens the Step 13 containerized worker runtime with three new layers:

- digest-pinned provenance
- bounded sandwich-style diagnostics
- static-first capability preflight with selective dynamic escalation

## Implementation Highlights

### 1. Repo-managed metadata registry

- Added `infra/worker_manifest.json`
- The registry is versioned in-repo and loaded through
  `v2_spring.runtime.worker_metadata`
- The runtime now records:
  - registry path
  - registry schema version
  - registry checksum

### 2. Digest-pinned runtime provenance

- The container worker Dockerfile now pins its base image by digest
- Receipts now include both:
  - logical image tag
  - resolved local image digest

### 3. Bounded diagnostics

- Added `container_log_capture.py` inside the worker image
- The capture wrapper records bounded stdout/stderr previews and byte counts
- Capture strategy is sandwich-style (`head + tail`) rather than tail-only
- Host receipt collection now copies only the bounded output artifacts produced
  by the wrapper

### 4. Capability preflight

- Static manifest checks validate:
  - required tool declaration
  - network allowance
  - multi-file context support
  - write scope support
  - output kind support
- Selected tools can also use a lightweight dynamic admission check before
  execution
- Mismatch produces a typed preflight refusal

### 5. Store integration

- Containerized dispatch now passes explicit `ExecutionRequirements` into the
  runtime
- Typed preflight refusals are converted into failed task receipts rather than
  bubbling up as ambiguous runtime errors

## Risk Handling

### Resolved in this step

- `RISK-0033` image integrity / replay drift
- `RISK-0034` bounded log hygiene and host copy-out risk
- `RISK-0035` runtime environment gap for the current containerized lane
- `RISK-0037` metadata snapshot fragmentation
- `RISK-0038` tail-only diagnostic blindspot

### Mitigating

- `RISK-0039` manifest vs reality gap
  - current mitigation: static-first checks plus selective dynamic admission

### Deferred

- `RISK-0036` image bloat / pull latency
  - remains a before-scale concern

## Verification

- `PYTHONPATH=src pytest -q tests/test_step14_containerized_worker.py tests/test_step13_containerized_worker.py`
- `python3 -m compileall src`
- `PYTHONPATH=src pytest -q`
