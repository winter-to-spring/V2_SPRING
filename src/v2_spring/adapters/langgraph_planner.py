from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass
from typing import Any, Protocol, TypedDict

from langgraph.graph import END, START, StateGraph
from pydantic import ValidationError

from v2_spring.domain.planner_adapter import (
    PLANNER_ADAPTER_OUTPUT_ADAPTER,
    PlannerAdapterOutput,
    PlannerContextWindow,
    PlannerTransportAuditView,
    PlannerTransportProvider,
)
from v2_spring.planner.proposals import PlannerAdapterFormatError

_CONTROL_CHARACTER_PATTERN = re.compile(r"[\x00-\x08\x0B-\x1F\x7F]+")
_PATH_PATTERN = re.compile(r"/Users/[^\s\"']+")
_SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),
    re.compile(r"(?i)(api[_-]?key|authorization|token)\s*[:=]\s*[^\s,;]+"),
]


@dataclass(frozen=True)
class StructuredTransportResponse:
    """One raw provider response plus bounded transport telemetry."""

    raw_response: Any
    provider: PlannerTransportProvider
    model: str
    response_id: str | None = None
    retry_count: int = 0
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None


@dataclass(frozen=True)
class PlannerAdapterInvocationResult:
    """Final parsed planner output with transport telemetry."""

    parsed_output: PlannerAdapterOutput
    format_failures: int
    transport_audit: PlannerTransportAuditView


class PlannerTransportError(RuntimeError):
    """Base error for provider/network failures at the adapter edge."""

    def __init__(
        self,
        message: str,
        *,
        code: str,
        provider: PlannerTransportProvider,
        model: str,
        retryable: bool,
        retry_count: int = 0,
        response_id: str | None = None,
        status_code: int | None = None,
        timeout_seconds: float | None = None,
        orphan_risk_possible: bool = False,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.provider = provider
        self.model = model
        self.retryable = retryable
        self.retry_count = retry_count
        self.response_id = response_id
        self.status_code = status_code
        self.timeout_seconds = timeout_seconds
        self.orphan_risk_possible = orphan_risk_possible


class PlannerTransportTimeoutError(PlannerTransportError):
    """Raised when the provider call times out."""


class PlannerTransportRateLimitError(PlannerTransportError):
    """Raised when the provider responds with a rate limit failure."""


class PlannerTransportNetworkError(PlannerTransportError):
    """Raised when the provider cannot be reached reliably."""


class PlannerTransportUnavailableError(PlannerTransportError):
    """Raised when the provider has a retryable 5xx-style outage."""


class PlannerTransportAuthenticationError(PlannerTransportError):
    """Raised when credentials or permissions are invalid."""


class PlannerTransportProviderResponseError(PlannerTransportError):
    """Raised when the provider returns an unusable response."""


class PlannerTransportCancelledError(PlannerTransportError):
    """Raised when the local caller interrupts the provider request."""


class StructuredPlannerTransport(Protocol):
    """Transport contract for any bounded structured planner backend."""

    def invoke(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        output_schema: dict[str, Any],
    ) -> StructuredTransportResponse: ...


class ScriptedStructuredPlannerTransport:
    """Deterministic transport used by CLI proofing and tests."""

    def __init__(self, responses: list[Any]) -> None:
        self._responses = list(responses)
        self._fallback_response = responses[-1] if responses else None

    def invoke(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        output_schema: dict[str, Any],
    ) -> StructuredTransportResponse:
        if not self._responses:
            if self._fallback_response is None:
                raise RuntimeError("No scripted planner responses remain for this invocation.")
            raw_response = self._fallback_response
        else:
            raw_response = self._responses.pop(0)
        return StructuredTransportResponse(
            raw_response=raw_response,
            provider=PlannerTransportProvider.SCRIPTED,
            model="scripted-proof",
            retry_count=0,
        )


class OpenAIStructuredPlannerTransport:
    """Concrete OpenAI-first transport behind a provider-agnostic seam."""

    def __init__(
        self,
        *,
        model: str,
        api_key: str | None = None,
        timeout_seconds: float = 30.0,
        max_retries: int = 2,
        backoff_seconds: float = 0.5,
        client: Any | None = None,
    ) -> None:
        self._model = model
        self._api_key = api_key
        self._timeout_seconds = timeout_seconds
        self._max_retries = max_retries
        self._backoff_seconds = backoff_seconds
        self._client = client

    def invoke(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        output_schema: dict[str, Any],
    ) -> StructuredTransportResponse:
        client = self._client or self._build_client()
        attempts = 0
        while True:
            try:
                response = client.chat.completions.create(
                    model=self._model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    response_format={
                        "type": "json_schema",
                        "json_schema": {
                            "name": "planner_adapter_output",
                            "strict": True,
                            "schema": output_schema,
                        },
                    },
                    temperature=0,
                    timeout=self._timeout_seconds,
                )
                return StructuredTransportResponse(
                    raw_response=self._extract_raw_content(response),
                    provider=PlannerTransportProvider.OPENAI,
                    model=getattr(response, "model", self._model) or self._model,
                    response_id=getattr(response, "id", None),
                    retry_count=attempts,
                    input_tokens=self._usage_field(response, "prompt_tokens"),
                    output_tokens=self._usage_field(response, "completion_tokens"),
                    total_tokens=self._usage_field(response, "total_tokens"),
                )
            except KeyboardInterrupt as exc:
                raise PlannerTransportCancelledError(
                    "Planner provider invocation was interrupted locally before completion.",
                    code="cancelled",
                    provider=PlannerTransportProvider.OPENAI,
                    model=self._model,
                    retryable=False,
                    retry_count=attempts,
                    timeout_seconds=self._timeout_seconds,
                    orphan_risk_possible=True,
                ) from exc
            except Exception as exc:  # pragma: no cover - exercised by fake client tests
                normalized = self._normalize_error(exc, retry_count=attempts)
                if normalized.retryable and attempts < self._max_retries:
                    time.sleep(self._backoff_seconds * (2**attempts))
                    attempts += 1
                    continue
                raise normalized from exc

    def _build_client(self) -> Any:
        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover - depends on optional dependency installation
            raise PlannerTransportProviderResponseError(
                "The openai package is not installed. Install project dependencies before using --provider openai.",
                code="client_not_installed",
                provider=PlannerTransportProvider.OPENAI,
                model=self._model,
                retryable=False,
            ) from exc

        kwargs: dict[str, Any] = {"max_retries": 0}
        if self._api_key is not None:
            kwargs["api_key"] = self._api_key
        return OpenAI(**kwargs)

    def _normalize_error(self, exc: Exception, *, retry_count: int) -> PlannerTransportError:
        name = exc.__class__.__name__
        status_code = getattr(exc, "status_code", None)
        message = _sanitize_text(str(exc) or name, limit=400)

        if name == "APITimeoutError":
            return PlannerTransportTimeoutError(
                f"OpenAI planner transport timed out: {message}",
                code="timeout",
                provider=PlannerTransportProvider.OPENAI,
                model=self._model,
                retryable=True,
                retry_count=retry_count,
                status_code=status_code,
                timeout_seconds=self._timeout_seconds,
            )
        if name == "RateLimitError" or status_code == 429:
            return PlannerTransportRateLimitError(
                f"OpenAI planner transport hit a rate limit: {message}",
                code="rate_limit",
                provider=PlannerTransportProvider.OPENAI,
                model=self._model,
                retryable=True,
                retry_count=retry_count,
                status_code=status_code,
                timeout_seconds=self._timeout_seconds,
            )
        if name == "APIConnectionError":
            return PlannerTransportNetworkError(
                f"OpenAI planner transport could not reach the provider: {message}",
                code="network",
                provider=PlannerTransportProvider.OPENAI,
                model=self._model,
                retryable=True,
                retry_count=retry_count,
                status_code=status_code,
                timeout_seconds=self._timeout_seconds,
            )
        if status_code in {401, 403} or name == "AuthenticationError":
            return PlannerTransportAuthenticationError(
                f"OpenAI planner transport authentication failed: {message}",
                code="authentication",
                provider=PlannerTransportProvider.OPENAI,
                model=self._model,
                retryable=False,
                retry_count=retry_count,
                status_code=status_code,
                timeout_seconds=self._timeout_seconds,
            )
        if isinstance(status_code, int) and status_code >= 500:
            return PlannerTransportUnavailableError(
                f"OpenAI planner transport is temporarily unavailable: {message}",
                code="provider_unavailable",
                provider=PlannerTransportProvider.OPENAI,
                model=self._model,
                retryable=True,
                retry_count=retry_count,
                status_code=status_code,
                timeout_seconds=self._timeout_seconds,
            )
        return PlannerTransportProviderResponseError(
            f"OpenAI planner transport failed with an unexpected provider response: {message}",
            code="provider_response",
            provider=PlannerTransportProvider.OPENAI,
            model=self._model,
            retryable=False,
            retry_count=retry_count,
            status_code=status_code,
            timeout_seconds=self._timeout_seconds,
        )

    @staticmethod
    def _usage_field(response: Any, field_name: str) -> int | None:
        usage = getattr(response, "usage", None)
        if usage is None:
            return None
        return getattr(usage, field_name, None)

    @staticmethod
    def _extract_raw_content(response: Any) -> Any:
        if not getattr(response, "choices", None):
            raise PlannerTransportProviderResponseError(
                "OpenAI planner transport returned no choices.",
                code="empty_choices",
                provider=PlannerTransportProvider.OPENAI,
                model=getattr(response, "model", "unknown"),
                retryable=False,
                response_id=getattr(response, "id", None),
            )
        message = response.choices[0].message
        if getattr(message, "refusal", None):
            raise PlannerTransportProviderResponseError(
                f"OpenAI planner transport returned a refusal: {_sanitize_text(message.refusal, limit=300)}",
                code="refusal",
                provider=PlannerTransportProvider.OPENAI,
                model=getattr(response, "model", "unknown"),
                retryable=False,
                response_id=getattr(response, "id", None),
            )
        content = getattr(message, "content", None)
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            text_parts = [item.get("text", "") for item in content if isinstance(item, dict)]
            if text_parts:
                return "".join(text_parts)
        raise PlannerTransportProviderResponseError(
            "OpenAI planner transport returned no structured message content.",
            code="missing_content",
            provider=PlannerTransportProvider.OPENAI,
            model=getattr(response, "model", "unknown"),
            retryable=False,
            response_id=getattr(response, "id", None),
        )


class AnthropicStructuredPlannerTransport:
    """Concrete Anthropic-style tool-use transport behind the same narrow seam."""

    def __init__(
        self,
        *,
        model: str,
        api_key: str | None = None,
        timeout_seconds: float = 30.0,
        max_retries: int = 2,
        backoff_seconds: float = 0.5,
        client: Any | None = None,
    ) -> None:
        self._model = model
        self._api_key = api_key
        self._timeout_seconds = timeout_seconds
        self._max_retries = max_retries
        self._backoff_seconds = backoff_seconds
        self._client = client

    def invoke(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        output_schema: dict[str, Any],
    ) -> StructuredTransportResponse:
        client = self._client or self._build_client()
        attempts = 0
        while True:
            try:
                response = client.messages.create(
                    model=self._model,
                    system=system_prompt,
                    messages=[
                        {
                            "role": "user",
                            "content": user_prompt,
                        },
                    ],
                    tools=[
                        {
                            "name": "planner_adapter_output",
                            "description": "Return one schema-valid planner output.",
                            "input_schema": output_schema,
                        },
                    ],
                    tool_choice={"type": "tool", "name": "planner_adapter_output"},
                    max_tokens=800,
                    temperature=0,
                    timeout=self._timeout_seconds,
                )
                return StructuredTransportResponse(
                    raw_response=self._extract_raw_content(response),
                    provider=PlannerTransportProvider.ANTHROPIC,
                    model=getattr(response, "model", self._model) or self._model,
                    response_id=getattr(response, "id", None),
                    retry_count=attempts,
                    input_tokens=self._usage_field(response, "input_tokens"),
                    output_tokens=self._usage_field(response, "output_tokens"),
                    total_tokens=self._total_tokens(response),
                )
            except KeyboardInterrupt as exc:
                raise PlannerTransportCancelledError(
                    "Anthropic planner transport was interrupted locally before completion.",
                    code="cancelled",
                    provider=PlannerTransportProvider.ANTHROPIC,
                    model=self._model,
                    retryable=False,
                    retry_count=attempts,
                    timeout_seconds=self._timeout_seconds,
                    orphan_risk_possible=True,
                ) from exc
            except Exception as exc:  # pragma: no cover - exercised by fake client tests
                normalized = self._normalize_error(exc, retry_count=attempts)
                if normalized.retryable and attempts < self._max_retries:
                    time.sleep(self._backoff_seconds * (2**attempts))
                    attempts += 1
                    continue
                raise normalized from exc

    def _build_client(self) -> Any:
        try:
            from anthropic import Anthropic
        except ImportError as exc:  # pragma: no cover - depends on optional dependency installation
            raise PlannerTransportProviderResponseError(
                "The anthropic package is not installed. Install project dependencies before using --provider anthropic.",
                code="client_not_installed",
                provider=PlannerTransportProvider.ANTHROPIC,
                model=self._model,
                retryable=False,
            ) from exc

        kwargs: dict[str, Any] = {}
        if self._api_key is not None:
            kwargs["api_key"] = self._api_key
        return Anthropic(**kwargs)

    def _normalize_error(self, exc: Exception, *, retry_count: int) -> PlannerTransportError:
        name = exc.__class__.__name__
        status_code = getattr(exc, "status_code", None)
        message = _sanitize_text(str(exc) or name, limit=400)

        if name in {"APITimeoutError", "TimeoutError"}:
            return PlannerTransportTimeoutError(
                f"Anthropic planner transport timed out: {message}",
                code="timeout",
                provider=PlannerTransportProvider.ANTHROPIC,
                model=self._model,
                retryable=True,
                retry_count=retry_count,
                status_code=status_code,
                timeout_seconds=self._timeout_seconds,
            )
        if name == "RateLimitError" or status_code == 429:
            return PlannerTransportRateLimitError(
                f"Anthropic planner transport hit a rate limit: {message}",
                code="rate_limit",
                provider=PlannerTransportProvider.ANTHROPIC,
                model=self._model,
                retryable=True,
                retry_count=retry_count,
                status_code=status_code,
                timeout_seconds=self._timeout_seconds,
            )
        if name in {"APIConnectionError", "APIError"} and status_code is None:
            return PlannerTransportNetworkError(
                f"Anthropic planner transport could not reach the provider: {message}",
                code="network",
                provider=PlannerTransportProvider.ANTHROPIC,
                model=self._model,
                retryable=True,
                retry_count=retry_count,
                status_code=status_code,
                timeout_seconds=self._timeout_seconds,
            )
        if status_code in {401, 403} or name == "AuthenticationError":
            return PlannerTransportAuthenticationError(
                f"Anthropic planner transport authentication failed: {message}",
                code="authentication",
                provider=PlannerTransportProvider.ANTHROPIC,
                model=self._model,
                retryable=False,
                retry_count=retry_count,
                status_code=status_code,
                timeout_seconds=self._timeout_seconds,
            )
        if isinstance(status_code, int) and status_code >= 500:
            return PlannerTransportUnavailableError(
                f"Anthropic planner transport is temporarily unavailable: {message}",
                code="provider_unavailable",
                provider=PlannerTransportProvider.ANTHROPIC,
                model=self._model,
                retryable=True,
                retry_count=retry_count,
                status_code=status_code,
                timeout_seconds=self._timeout_seconds,
            )
        return PlannerTransportProviderResponseError(
            f"Anthropic planner transport failed with an unexpected provider response: {message}",
            code="provider_response",
            provider=PlannerTransportProvider.ANTHROPIC,
            model=self._model,
            retryable=False,
            retry_count=retry_count,
            status_code=status_code,
            timeout_seconds=self._timeout_seconds,
        )

    @staticmethod
    def _usage_field(response: Any, field_name: str) -> int | None:
        usage = getattr(response, "usage", None)
        if usage is None:
            return None
        return getattr(usage, field_name, None)

    @classmethod
    def _total_tokens(cls, response: Any) -> int | None:
        input_tokens = cls._usage_field(response, "input_tokens")
        output_tokens = cls._usage_field(response, "output_tokens")
        if input_tokens is None and output_tokens is None:
            return None
        return (input_tokens or 0) + (output_tokens or 0)

    @staticmethod
    def _extract_raw_content(response: Any) -> Any:
        content = getattr(response, "content", None) or []
        for block in content:
            block_type = getattr(block, "type", None) or (block.get("type") if isinstance(block, dict) else None)
            block_name = getattr(block, "name", None) or (block.get("name") if isinstance(block, dict) else None)
            if block_type == "tool_use" and block_name == "planner_adapter_output":
                if isinstance(block, dict):
                    return block.get("input")
                return getattr(block, "input", None)
        for block in content:
            block_type = getattr(block, "type", None) or (block.get("type") if isinstance(block, dict) else None)
            if block_type == "text":
                text = getattr(block, "text", None) or (block.get("text") if isinstance(block, dict) else None)
                if text:
                    raise PlannerTransportProviderResponseError(
                        f"Anthropic planner transport returned text instead of tool output: {_sanitize_text(text, limit=300)}",
                        code="missing_tool_use",
                        provider=PlannerTransportProvider.ANTHROPIC,
                        model=getattr(response, "model", "unknown"),
                        retryable=False,
                        response_id=getattr(response, "id", None),
                    )
        raise PlannerTransportProviderResponseError(
            "Anthropic planner transport returned no planner_adapter_output tool use block.",
            code="missing_tool_use",
            provider=PlannerTransportProvider.ANTHROPIC,
            model=getattr(response, "model", "unknown"),
            retryable=False,
            response_id=getattr(response, "id", None),
        )


class PlannerGraphState(TypedDict, total=False):
    context: PlannerContextWindow
    transport_response: StructuredTransportResponse
    transport_audit: PlannerTransportAuditView
    parsed_output: PlannerAdapterOutput
    format_failures: int
    parse_errors: list[str]


class LangGraphPlannerAdapter:
    """Bounded LangGraph planner wrapper around a structured planner transport."""

    def __init__(
        self,
        *,
        transport: StructuredPlannerTransport,
        max_format_retries: int = 1,
        max_user_prompt_chars: int = 12_000,
    ) -> None:
        self._transport = transport
        self._max_format_retries = max_format_retries
        self._max_user_prompt_chars = max_user_prompt_chars
        self._compiled = self._build_graph().compile()

    def invoke(self, context: PlannerContextWindow) -> PlannerAdapterInvocationResult:
        state = self._compiled.invoke(
            {
                "context": context,
                "format_failures": 0,
                "parse_errors": [],
            },
        )
        parsed = state.get("parsed_output")
        if parsed is None:
            parse_errors = state.get("parse_errors", [])
            raise PlannerAdapterFormatError(
                "Planner adapter could not parse a schema-valid structured response. "
                f"Observed parse errors: {parse_errors}",
                transport_audit=state.get("transport_audit"),
            )
        transport_audit = state.get("transport_audit")
        if transport_audit is None:
            raise RuntimeError("Planner transport audit metadata was not recorded.")
        return PlannerAdapterInvocationResult(
            parsed_output=parsed,
            format_failures=state.get("format_failures", 0),
            transport_audit=transport_audit,
        )

    def _build_graph(self) -> StateGraph[PlannerGraphState]:
        graph = StateGraph(PlannerGraphState)
        graph.add_node("invoke_transport", self._invoke_transport)
        graph.add_node("parse_output", self._parse_output)
        graph.add_edge(START, "invoke_transport")
        graph.add_edge("invoke_transport", "parse_output")
        graph.add_conditional_edges(
            "parse_output",
            self._next_after_parse,
            {
                "retry": "invoke_transport",
                "done": END,
            },
        )
        return graph

    def _invoke_transport(self, state: PlannerGraphState) -> PlannerGraphState:
        context = state["context"]
        system_prompt = self._build_system_prompt()
        user_prompt, truncated = self._build_user_prompt(context, parse_errors=state.get("parse_errors", []))
        response = self._transport.invoke(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            output_schema=PLANNER_ADAPTER_OUTPUT_ADAPTER.json_schema(),
        )
        transport_audit = PlannerTransportAuditView(
            provider=response.provider,
            model=response.model,
            response_id=response.response_id,
            retry_count=response.retry_count,
            truncated=truncated,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            total_tokens=response.total_tokens,
            system_prompt_hash=_sha256(system_prompt),
            user_prompt_hash=_sha256(user_prompt),
            user_prompt_chars=len(user_prompt),
        )
        return {
            "transport_response": response,
            "transport_audit": transport_audit,
        }

    def _parse_output(self, state: PlannerGraphState) -> PlannerGraphState:
        transport_response = state.get("transport_response")
        if transport_response is None:
            raise RuntimeError("Planner graph is missing the provider response.")
        raw_response = transport_response.raw_response
        normalized = raw_response
        if isinstance(raw_response, str):
            normalized = json.loads(raw_response)
        try:
            parsed = PLANNER_ADAPTER_OUTPUT_ADAPTER.validate_python(normalized)
        except (ValidationError, json.JSONDecodeError) as exc:
            return {
                "format_failures": state.get("format_failures", 0) + 1,
                "parse_errors": [*state.get("parse_errors", []), _sanitize_text(str(exc), limit=500)],
            }
        return {"parsed_output": parsed}

    def _next_after_parse(self, state: PlannerGraphState) -> str:
        if state.get("parsed_output") is not None:
            return "done"
        if state.get("format_failures", 0) <= self._max_format_retries:
            return "retry"
        return "done"

    @staticmethod
    def _build_system_prompt() -> str:
        return (
            "You are the bounded planner for V2_SPRING. "
            "Return only schema-valid structured output that matches the discriminated union. "
            "Use an action proposal when a safe legal move exists. "
            "Use escalation only after checking the available legal actions and identifying a concrete founder-facing blocker. "
            "Do not fabricate missing state. "
            "Use analysis_summary to explain the decision briefly without hidden chain-of-thought."
        )

    def _build_user_prompt(
        self,
        context: PlannerContextWindow,
        *,
        parse_errors: list[str],
    ) -> tuple[str, bool]:
        payload = self._sanitize_payload(context.model_dump(mode="json"))
        if parse_errors:
            payload["adapter_feedback"] = {
                "previous_parse_errors": [_sanitize_text(item, limit=220) for item in parse_errors[-2:]],
                "instruction": (
                    "Return one schema-valid response. Do not mix action and escalation fields. "
                    "Use the discriminator field `kind` first."
                ),
            }

        serialized = json.dumps(payload, ensure_ascii=False, indent=2)
        if len(serialized) <= self._max_user_prompt_chars:
            return serialized, False

        truncated_payload = json.loads(serialized)
        truncated = True

        truncation_steps = [
            lambda item: self._trim_list(item, "founder_interventions", keep=2),
            lambda item: self._trim_list(item, "recent_attempts", keep=3),
            lambda item: self._shrink_failure_report(item),
            lambda item: self._trim_list(item, "founder_interventions", keep=1),
            lambda item: self._trim_list(item, "recent_attempts", keep=1),
            lambda item: self._clear_list(item, "founder_interventions"),
            lambda item: self._clear_list(item, "recent_attempts"),
        ]
        for step in truncation_steps:
            step(truncated_payload)
            serialized = json.dumps(truncated_payload, ensure_ascii=False, indent=2)
            if len(serialized) <= self._max_user_prompt_chars:
                return serialized, truncated

        fallback_payload = {
            "snapshot": truncated_payload["snapshot"],
            "legal_actions": truncated_payload["legal_actions"],
            "masked_actions": truncated_payload["masked_actions"],
            "failure_report": truncated_payload.get("failure_report"),
            "adapter_feedback": truncated_payload.get("adapter_feedback"),
        }
        serialized = json.dumps(fallback_payload, ensure_ascii=False, indent=2)
        if len(serialized) > self._max_user_prompt_chars:
            serialized = serialized[: self._max_user_prompt_chars - 3] + "..."
        return serialized, truncated

    @classmethod
    def _sanitize_payload(cls, value: Any) -> Any:
        if isinstance(value, str):
            return _sanitize_text(value, limit=900)
        if isinstance(value, list):
            return [cls._sanitize_payload(item) for item in value]
        if isinstance(value, dict):
            return {key: cls._sanitize_payload(item) for key, item in value.items()}
        return value

    @staticmethod
    def _trim_list(payload: dict[str, Any], key: str, *, keep: int) -> None:
        values = payload.get(key)
        if isinstance(values, list) and len(values) > keep:
            payload[key] = values[-keep:]

    @staticmethod
    def _clear_list(payload: dict[str, Any], key: str) -> None:
        values = payload.get(key)
        if isinstance(values, list):
            payload[key] = []

    @staticmethod
    def _shrink_failure_report(payload: dict[str, Any]) -> None:
        report = payload.get("failure_report")
        if not isinstance(report, dict):
            return
        if isinstance(report.get("previous_rationale"), str):
            report["previous_rationale"] = _sanitize_text(report["previous_rationale"], limit=250)
        if isinstance(report.get("short_traceback"), str):
            report["short_traceback"] = _sanitize_text(report["short_traceback"], limit=180)
        if isinstance(report.get("observed_outcome"), str):
            report["observed_outcome"] = _sanitize_text(report["observed_outcome"], limit=240)


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sanitize_text(value: str, *, limit: int) -> str:
    cleaned = _CONTROL_CHARACTER_PATTERN.sub(" ", value)
    cleaned = _PATH_PATTERN.sub("<path>", cleaned)
    for pattern in _SECRET_PATTERNS:
        cleaned = pattern.sub("<redacted>", cleaned)
    cleaned = " ".join(cleaned.split())
    if len(cleaned) > limit:
        return cleaned[: limit - 3] + "..."
    return cleaned
