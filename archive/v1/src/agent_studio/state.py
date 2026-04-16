from __future__ import annotations

from typing import Literal, TypedDict


QualityStatus = Literal["unknown", "pass", "fail"]


Phase = Literal[
    "inbox",
    "requirements_drafting",
    "planning",
    "implementation",
    "module_verification",
    "completed",
]


class AgentStudioState(TypedDict):
    request_id: str
    goal: str
    current_phase: Phase
    current_owner: str
    status: str
    prd_path: str
    roadmap_path: str
    test_report_path: str
    lint: QualityStatus
    typecheck: QualityStatus
    unit: QualityStatus
    module_smoke: QualityStatus
    requirements_approved: bool
    release_approved: bool
    last_action: str
    blocker: str
