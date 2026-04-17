from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, field_validator

from v2_spring.domain.run import RunStatus
from v2_spring.domain.snapshot import PossibleActionName, RunSnapshotView


class ExecutionRuntime(StrEnum):
    """Concrete execution runtimes hidden behind the control-plane dispatcher."""

    BOUNDED_LOCAL = "bounded_local"
    ISOLATED_WORKER = "isolated_worker"
    CREWAI_TEAM = "crewai_team"


class TaskComplexity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class WriteScope(StrEnum):
    NONE = "none"
    SINGLE_FILE = "single_file"
    MULTI_FILE = "multi_file"


class ExpectedOutputKind(StrEnum):
    ARTIFACT_ONLY = "artifact_only"
    UNIFIED_PATCH = "unified_patch"
    PATCH_AND_ARTIFACT = "patch_and_artifact"


class RoutingRefusalCode(StrEnum):
    NO_ROUTABLE_WORK = "no_routable_work"
    CAPABILITY_EXCEEDED = "capability_exceeded"
    NO_MATCHING_RUNTIME = "no_matching_runtime"


class ExecutionRequirements(BaseModel):
    """Planner-facing execution requirements; these are hints, not direct authority."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    task_complexity: TaskComplexity
    needs_isolation: bool = False
    requires_network: bool = False
    needs_multi_file_context: bool = False
    write_scope: WriteScope = WriteScope.NONE
    expected_output_kind: ExpectedOutputKind


class SystemLimits(BaseModel):
    """Founder/system caps enforced by the dispatcher before routing."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    max_task_complexity: TaskComplexity = TaskComplexity.MEDIUM
    allow_network: bool = False
    allow_isolated_worker: bool = True
    available_runtimes: tuple[ExecutionRuntime, ...] = (
        ExecutionRuntime.BOUNDED_LOCAL,
        ExecutionRuntime.ISOLATED_WORKER,
    )

    @field_validator("available_runtimes")
    @classmethod
    def ensure_unique_runtimes(
        cls,
        value: tuple[ExecutionRuntime, ...],
    ) -> tuple[ExecutionRuntime, ...]:
        if len(value) != len(set(value)):
            raise ValueError("available_runtimes must not contain duplicates")
        if not value:
            raise ValueError("available_runtimes must not be empty")
        return value


class RoutingDecision(BaseModel):
    """Deterministic routing outcome for an execution request."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["decision"] = "decision"
    runtime: ExecutionRuntime
    matched_policy: str = Field(min_length=1, max_length=120)
    rationale: str = Field(min_length=1, max_length=1000)
    original_requirements: ExecutionRequirements
    normalized_requirements: ExecutionRequirements
    guard_notes: list[str] = Field(default_factory=list)

    @field_validator("matched_policy", "rationale")
    @classmethod
    def ensure_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("value must not be blank")
        return cleaned


class RoutingRefusalReceipt(BaseModel):
    """Expected refusal path when dispatcher cannot legally route the request."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["refusal"] = "refusal"
    refusal_code: RoutingRefusalCode
    message: str = Field(min_length=1, max_length=1000)
    next_step_hint: str = Field(min_length=1, max_length=1000)
    escalation_recommended: bool = True
    original_requirements: ExecutionRequirements | None = None
    normalized_requirements: ExecutionRequirements | None = None
    guard_notes: list[str] = Field(default_factory=list)

    @field_validator("message", "next_step_hint")
    @classmethod
    def ensure_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("value must not be blank")
        return cleaned


RoutingOutcome = Annotated[RoutingDecision | RoutingRefusalReceipt, Field(discriminator="kind")]
ROUTING_OUTCOME_ADAPTER = TypeAdapter(RoutingOutcome)


class RoutingInspectionView(BaseModel):
    """Founder/operator-facing route inspection bundle."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: UUID
    snapshot_hash: str = Field(min_length=64, max_length=64)
    source_action: PossibleActionName | None
    source_action_reason: str | None = Field(default=None, max_length=400)
    requirements: ExecutionRequirements | None = None
    system_limits: SystemLimits
    outcome: RoutingOutcome
    recorded_observation_id: UUID | None = None

    @field_validator("snapshot_hash")
    @classmethod
    def ensure_hash(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if len(cleaned) != 64 or any(character not in "0123456789abcdef" for character in cleaned):
            raise ValueError("snapshot_hash must be a 64-character hexadecimal string")
        return cleaned

    @field_validator("source_action_reason")
    @classmethod
    def ensure_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("value must not be blank when provided")
        return cleaned


def default_system_limits() -> SystemLimits:
    """Return the current founder/system policy defaults for execution routing."""

    return SystemLimits()


def default_requirements_for_bounded_execution() -> ExecutionRequirements:
    """Current deterministic default for the existing bounded executor lane."""

    return ExecutionRequirements(
        task_complexity=TaskComplexity.LOW,
        needs_isolation=False,
        requires_network=False,
        needs_multi_file_context=False,
        write_scope=WriteScope.NONE,
        expected_output_kind=ExpectedOutputKind.ARTIFACT_ONLY,
    )


def route_task(
    requirements: ExecutionRequirements,
    system_limits: SystemLimits,
) -> RoutingOutcome:
    """Deterministically map planner requirements to a concrete execution runtime.

    This function must remain pure. It should not read the database, touch the
    filesystem, or call any provider/API. The control plane may wrap it with
    richer inspection/audit behavior, but the core route decision must stay a
    fast, side-effect-free policy function.
    """

    normalized_requirements, guard_notes = _normalize_requirements(requirements)
    capability_refusal = _check_capability_limits(
        original=requirements,
        normalized=normalized_requirements,
        system_limits=system_limits,
        guard_notes=guard_notes,
    )
    if capability_refusal is not None:
        return capability_refusal

    if (
        ExecutionRuntime.BOUNDED_LOCAL in system_limits.available_runtimes
        and _fits_bounded_local(normalized_requirements)
    ):
        rationale = (
            "The request fits the cheap bounded local lane: read-only, offline, and low-complexity."
        )
        return RoutingDecision(
            runtime=ExecutionRuntime.BOUNDED_LOCAL,
            matched_policy="bounded_local_read_only_rule",
            rationale=rationale,
            original_requirements=requirements,
            normalized_requirements=normalized_requirements,
            guard_notes=guard_notes,
        )

    if (
        ExecutionRuntime.ISOLATED_WORKER in system_limits.available_runtimes
        and _fits_isolated_worker(normalized_requirements)
    ):
        rationale = (
            "The request exceeds the bounded local lane but still fits the isolated worker proof boundary."
        )
        return RoutingDecision(
            runtime=ExecutionRuntime.ISOLATED_WORKER,
            matched_policy="isolated_worker_bounded_patch_rule",
            rationale=rationale,
            original_requirements=requirements,
            normalized_requirements=normalized_requirements,
            guard_notes=guard_notes,
        )

    return RoutingRefusalReceipt(
        refusal_code=RoutingRefusalCode.NO_MATCHING_RUNTIME,
        message=(
            "No currently registered execution runtime can satisfy the normalized requirements safely."
        ),
        next_step_hint=(
            "Adjust the task requirements, open a founder escalation, or wait until a richer runtime is added."
        ),
        original_requirements=requirements,
        normalized_requirements=normalized_requirements,
        guard_notes=guard_notes,
    )


def derive_requirements_for_snapshot(snapshot: RunSnapshotView) -> ExecutionRequirements | None:
    """Return the default execution requirements implied by the current run state."""

    if (
        snapshot.run.status == RunStatus.READY
        and snapshot.task_summary.created == 0
        and snapshot.task_summary.running == 0
    ):
        return default_requirements_for_bounded_execution()
    return None


def _normalize_requirements(
    requirements: ExecutionRequirements,
) -> tuple[ExecutionRequirements, list[str]]:
    normalized = requirements
    notes: list[str] = []

    if (
        requirements.task_complexity == TaskComplexity.HIGH
        and not requirements.requires_network
        and not requirements.needs_multi_file_context
        and requirements.write_scope == WriteScope.NONE
        and requirements.expected_output_kind == ExpectedOutputKind.ARTIFACT_ONLY
    ):
        normalized = requirements.model_copy(
            update={"task_complexity": TaskComplexity.LOW},
        )
        notes.append(
            "task_complexity was downgraded from high to low because the request is read-only, offline, and artifact-only.",
        )
    elif (
        requirements.task_complexity == TaskComplexity.HIGH
        and not requirements.requires_network
        and not requirements.needs_multi_file_context
        and requirements.write_scope == WriteScope.SINGLE_FILE
    ):
        normalized = requirements.model_copy(
            update={"task_complexity": TaskComplexity.MEDIUM},
        )
        notes.append(
            "task_complexity was downgraded from high to medium because the request is a bounded single-file change.",
        )

    return normalized, notes


def _check_capability_limits(
    *,
    original: ExecutionRequirements,
    normalized: ExecutionRequirements,
    system_limits: SystemLimits,
    guard_notes: list[str],
) -> RoutingRefusalReceipt | None:
    if normalized.requires_network and not system_limits.allow_network:
        return RoutingRefusalReceipt(
            refusal_code=RoutingRefusalCode.CAPABILITY_EXCEEDED,
            message="The requested execution requires network access beyond the current founder/system policy.",
            next_step_hint="Remove the network requirement or escalate for a higher-capability runtime policy.",
            original_requirements=original,
            normalized_requirements=normalized,
            guard_notes=guard_notes,
        )

    if normalized.needs_isolation and not system_limits.allow_isolated_worker:
        return RoutingRefusalReceipt(
            refusal_code=RoutingRefusalCode.CAPABILITY_EXCEEDED,
            message="The request requires isolated worker privileges that are not enabled in the current system policy.",
            next_step_hint="Lower the isolation requirement or ask the founder to widen the allowed capability set.",
            original_requirements=original,
            normalized_requirements=normalized,
            guard_notes=guard_notes,
        )

    if _complexity_rank(normalized.task_complexity) > _complexity_rank(system_limits.max_task_complexity):
        return RoutingRefusalReceipt(
            refusal_code=RoutingRefusalCode.CAPABILITY_EXCEEDED,
            message=(
                f"Normalized task complexity {normalized.task_complexity.value} exceeds the current maximum "
                f"allowed complexity {system_limits.max_task_complexity.value}."
            ),
            next_step_hint="Reduce the requested scope or ask the founder to widen execution complexity limits.",
            original_requirements=original,
            normalized_requirements=normalized,
            guard_notes=guard_notes,
        )

    return None


def _fits_bounded_local(requirements: ExecutionRequirements) -> bool:
    return (
        requirements.task_complexity == TaskComplexity.LOW
        and not requirements.needs_isolation
        and not requirements.requires_network
        and not requirements.needs_multi_file_context
        and requirements.write_scope == WriteScope.NONE
        and requirements.expected_output_kind == ExpectedOutputKind.ARTIFACT_ONLY
    )


def _fits_isolated_worker(requirements: ExecutionRequirements) -> bool:
    return (
        _complexity_rank(requirements.task_complexity) <= _complexity_rank(TaskComplexity.MEDIUM)
        and not requirements.requires_network
        and requirements.expected_output_kind
        in {
            ExpectedOutputKind.ARTIFACT_ONLY,
            ExpectedOutputKind.UNIFIED_PATCH,
            ExpectedOutputKind.PATCH_AND_ARTIFACT,
        }
    )


def _complexity_rank(value: TaskComplexity) -> int:
    order = {
        TaskComplexity.LOW: 0,
        TaskComplexity.MEDIUM: 1,
        TaskComplexity.HIGH: 2,
    }
    return order[value]
