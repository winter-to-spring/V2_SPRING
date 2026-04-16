from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from v2_spring.domain.planner_adapter import PlannerTransportAuditView


class StalePlannerProposalError(ValueError):
    """Raised when a proposal was created against an old snapshot hash."""


class PlannerStaleQuotaExhaustedError(PermissionError):
    """Raised when repeated stale attempts exhaust the separate stale quota."""


class IllegalPlannerProposalError(PermissionError):
    """Raised when the selected action is not currently legal for the run."""


class TransportDuplicatePlannerProposalError(PermissionError):
    """Raised when the same submission key is replayed within one phase."""


class CognitiveDuplicatePlannerProposalError(PermissionError):
    """Raised when the planner repeats the same proposal content in one phase."""


class PlannerPhaseExhaustedError(PermissionError):
    """Raised when the current phase has no planner attempt budget left."""


class PlannerAdapterFormatError(ValueError):
    """Raised when the planner adapter cannot parse a structured response."""

    def __init__(
        self,
        message: str,
        *,
        transport_audit: "PlannerTransportAuditView | None" = None,
    ) -> None:
        super().__init__(message)
        self.transport_audit = transport_audit
