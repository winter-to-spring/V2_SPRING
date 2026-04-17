from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

from pydantic import BaseModel, ConfigDict, Field, field_validator


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class PatchApplyOutcome(StrEnum):
    APPLIED = "applied"
    BASE_HASH_CONFLICT = "base_hash_conflict"
    APPLY_CHECK_FAILED = "apply_check_failed"
    VALIDATION_FAILED = "validation_failed"


class PatchApplyReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    workspace: str = Field(min_length=1, max_length=4000)
    patch_sha256: str = Field(min_length=64, max_length=64)
    changed_files: list[str]
    validation_command: str = Field(min_length=1, max_length=400)
    outcome: PatchApplyOutcome
    summary: str = Field(min_length=1, max_length=2000)
    started_at: datetime
    finished_at: datetime
    base_hash_conflicts: list[str] = Field(default_factory=list)
    apply_check_stderr: str = ""
    validation_returncode: int | None = None
    validation_stdout_preview: str = ""
    validation_stderr_preview: str = ""

    @field_validator(
        "workspace",
        "patch_sha256",
        "validation_command",
        "summary",
        "apply_check_stderr",
        "validation_stdout_preview",
        "validation_stderr_preview",
    )
    @classmethod
    def ensure_text(cls, value: str) -> str:
        return value.rstrip()

    @field_validator("changed_files", "base_hash_conflicts")
    @classmethod
    def ensure_paths(cls, value: list[str]) -> list[str]:
        cleaned_values: list[str] = []
        for item in value:
            cleaned = item.strip()
            if not cleaned:
                raise ValueError("path entries must not be blank")
            cleaned_values.append(cleaned)
        return cleaned_values


def apply_patch_strict(
    *,
    workspace: Path,
    patch_body: str,
    patch_sha256: str,
    changed_files: list[str],
    base_file_hashes: dict[str, str],
) -> PatchApplyReceipt:
    workspace = workspace.expanduser().resolve()
    started_at = utc_now()
    validation_command = _build_validation_command(workspace)
    conflicts = _find_base_hash_conflicts(
        workspace=workspace,
        changed_files=changed_files,
        base_file_hashes=base_file_hashes,
    )
    if conflicts:
        finished_at = utc_now()
        return PatchApplyReceipt(
            workspace=str(workspace),
            patch_sha256=patch_sha256,
            changed_files=changed_files,
            validation_command=validation_command,
            outcome=PatchApplyOutcome.BASE_HASH_CONFLICT,
            summary="Patch intake was rejected because the current workspace no longer matches the worker base hashes.",
            started_at=started_at,
            finished_at=finished_at,
            base_hash_conflicts=conflicts,
        )

    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".patch", delete=False) as handle:
        handle.write(patch_body)
        patch_file = Path(handle.name)

    try:
        check = subprocess.run(
            ["git", "-C", str(workspace), "apply", "--check", str(patch_file)],
            capture_output=True,
            text=True,
            check=False,
        )
        if check.returncode != 0:
            finished_at = utc_now()
            return PatchApplyReceipt(
                workspace=str(workspace),
                patch_sha256=patch_sha256,
                changed_files=changed_files,
                validation_command=validation_command,
                outcome=PatchApplyOutcome.APPLY_CHECK_FAILED,
                summary="Patch intake was rejected because strict apply check failed against the current workspace.",
                started_at=started_at,
                finished_at=finished_at,
                apply_check_stderr=check.stderr[-4000:].rstrip(),
            )

        apply_result = subprocess.run(
            ["git", "-C", str(workspace), "apply", str(patch_file)],
            capture_output=True,
            text=True,
            check=False,
        )
        if apply_result.returncode != 0:
            finished_at = utc_now()
            return PatchApplyReceipt(
                workspace=str(workspace),
                patch_sha256=patch_sha256,
                changed_files=changed_files,
                validation_command=validation_command,
                outcome=PatchApplyOutcome.APPLY_CHECK_FAILED,
                summary="Patch intake was rejected because strict apply failed during execution.",
                started_at=started_at,
                finished_at=finished_at,
                apply_check_stderr=(apply_result.stderr or check.stderr)[-4000:].rstrip(),
            )

        validation = subprocess.run(
            validation_command.split(),
            cwd=str(workspace),
            capture_output=True,
            text=True,
            check=False,
        )
        if validation.returncode != 0:
            rollback = subprocess.run(
                ["git", "-C", str(workspace), "apply", "-R", str(patch_file)],
                capture_output=True,
                text=True,
                check=False,
            )
            if rollback.returncode != 0:
                raise RuntimeError(
                    "Patch validation failed and rollback failed; manual cleanup is required. "
                    f"rollback_stderr={rollback.stderr.strip()}",
                )
            finished_at = utc_now()
            return PatchApplyReceipt(
                workspace=str(workspace),
                patch_sha256=patch_sha256,
                changed_files=changed_files,
                validation_command=validation_command,
                outcome=PatchApplyOutcome.VALIDATION_FAILED,
                summary="Patch applied syntactically but failed bounded validation and was rolled back.",
                started_at=started_at,
                finished_at=finished_at,
                validation_returncode=validation.returncode,
                validation_stdout_preview=validation.stdout[-4000:].rstrip(),
                validation_stderr_preview=validation.stderr[-4000:].rstrip(),
            )

        finished_at = utc_now()
        return PatchApplyReceipt(
            workspace=str(workspace),
            patch_sha256=patch_sha256,
            changed_files=changed_files,
            validation_command=validation_command,
            outcome=PatchApplyOutcome.APPLIED,
            summary="Patch was applied strictly and passed bounded validation.",
            started_at=started_at,
            finished_at=finished_at,
            validation_returncode=validation.returncode,
            validation_stdout_preview=validation.stdout[-4000:].rstrip(),
            validation_stderr_preview=validation.stderr[-4000:].rstrip(),
        )
    finally:
        patch_file.unlink(missing_ok=True)


def _build_validation_command(workspace: Path) -> str:
    target = "src" if (workspace / "src").is_dir() else "."
    return f"python3 -m compileall {target}"


def _find_base_hash_conflicts(
    *,
    workspace: Path,
    changed_files: list[str],
    base_file_hashes: dict[str, str],
) -> list[str]:
    conflicts: list[str] = []
    for relative_path in changed_files:
        expected_hash = base_file_hashes.get(relative_path)
        if expected_hash is None:
            conflicts.append(relative_path)
            continue
        current_path = workspace / relative_path
        if not current_path.exists():
            conflicts.append(relative_path)
            continue
        current_hash = hashlib.sha256(current_path.read_bytes()).hexdigest()
        if current_hash != expected_hash:
            conflicts.append(relative_path)
    return conflicts
