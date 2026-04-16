from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from v2_spring.domain.approval import ApprovalView
from v2_spring.domain.artifact import ArtifactView
from v2_spring.domain.decision import DecisionView
from v2_spring.domain.observation import ObservationView
from v2_spring.domain.planner_attempt import PlannerAttemptView
from v2_spring.domain.run import RunView
from v2_spring.domain.task import TaskView


class ArtifactInspectionView(BaseModel):
    """Artifact projection enriched with current filesystem integrity checks."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    artifact: ArtifactView
    file_exists: bool
    hash_matches: bool | None


class TaskReplayView(BaseModel):
    """Replay projection for one task and its linked outcomes."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    task: TaskView
    decision: DecisionView | None
    artifacts: list[ArtifactInspectionView]
    observations: list[ObservationView]


class RunReplayView(BaseModel):
    """Stable replay/read-model projection for one run."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    run: RunView
    approvals: list[ApprovalView]
    decisions: list[DecisionView]
    tasks: list[TaskReplayView]
    planner_attempts: list[PlannerAttemptView]
    observations: list[ObservationView]
    orphan_artifacts: list[ArtifactInspectionView]
    consistency_warnings: list[str]
