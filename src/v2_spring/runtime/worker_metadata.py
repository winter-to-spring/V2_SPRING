from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


_METADATA_ENV_VAR = "V2_SPRING_WORKER_MANIFEST_PATH"
_DEFAULT_METADATA_PATH = Path(__file__).resolve().parents[3] / "infra" / "worker_manifest.json"


class WorkerLogCapturePolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    strategy: Literal["sandwich"]
    max_bytes: int = Field(ge=512, le=1_000_000)
    head_bytes: int = Field(ge=128, le=500_000)
    tail_bytes: int = Field(ge=128, le=500_000)

    @field_validator("tail_bytes")
    @classmethod
    def validate_total_budget(cls, value: int, info) -> int:
        head_bytes = info.data.get("head_bytes")
        max_bytes = info.data.get("max_bytes")
        if head_bytes is not None and max_bytes is not None and head_bytes + value > max_bytes:
            raise ValueError("head_bytes + tail_bytes must not exceed max_bytes")
        return value


class ContainerRuntimeManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    runtime: Literal["containerized_worker"]
    worker_image_tag: str = Field(min_length=1, max_length=200)
    base_image_reference: str = Field(min_length=1, max_length=400)
    required_tools: list[str] = Field(default_factory=list)
    allow_network: bool = False
    supports_multi_file_context: bool = False
    supported_write_scopes: list[str] = Field(default_factory=list)
    supported_output_kinds: list[str] = Field(default_factory=list)
    log_capture: WorkerLogCapturePolicy
    dynamic_admission_tools: list[str] = Field(default_factory=list)

    @field_validator("required_tools", "supported_write_scopes", "supported_output_kinds", "dynamic_admission_tools")
    @classmethod
    def ensure_unique_nonblank_items(cls, value: list[str]) -> list[str]:
        cleaned: list[str] = []
        for item in value:
            normalized = item.strip()
            if not normalized:
                raise ValueError("list items must not be blank")
            cleaned.append(normalized)
        if len(cleaned) != len(set(cleaned)):
            raise ValueError("list items must be unique")
        return cleaned


class WorkerMetadataRegistry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: int = Field(ge=1, le=100)
    registry_name: str = Field(min_length=1, max_length=120)
    runtimes: dict[str, ContainerRuntimeManifest]


class LoadedWorkerMetadataRegistry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    path: str = Field(min_length=1, max_length=4000)
    checksum: str = Field(min_length=64, max_length=64)
    registry: WorkerMetadataRegistry


def metadata_registry_path() -> Path:
    raw = os.environ.get(_METADATA_ENV_VAR)
    if raw:
        return Path(raw).expanduser().resolve()
    return _DEFAULT_METADATA_PATH


def load_worker_metadata_registry() -> LoadedWorkerMetadataRegistry:
    path = metadata_registry_path()
    if not path.exists():
        raise FileNotFoundError(f"Worker metadata registry {path} does not exist.")
    raw_bytes = path.read_bytes()
    payload = json.loads(raw_bytes.decode("utf-8"))
    registry = WorkerMetadataRegistry.model_validate(payload)
    return LoadedWorkerMetadataRegistry(
        path=str(path),
        checksum=sha256(raw_bytes).hexdigest(),
        registry=registry,
    )
