from __future__ import annotations


class StalePlannerProposalError(ValueError):
    """Raised when a proposal was created against an old snapshot hash."""


class IllegalPlannerProposalError(PermissionError):
    """Raised when the selected action is not currently legal for the run."""
