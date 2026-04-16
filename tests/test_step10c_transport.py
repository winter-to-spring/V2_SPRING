from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from v2_spring.adapters.langgraph_planner import (
    LangGraphPlannerAdapter,
    OpenAIStructuredPlannerTransport,
    ScriptedStructuredPlannerTransport,
)
from v2_spring.domain.approval import ApprovalStatus
from v2_spring.domain.planner_adapter import PlannerTransportProvider
from v2_spring.domain.run import RunCreateInput
from v2_spring.ledger.store import LedgerStore


def _make_store(tmp_path: Path) -> LedgerStore:
    return LedgerStore(f"sqlite+pysqlite:///{tmp_path / 'step10c.db'}")


def _approved_planner_context(tmp_path: Path):
    store = _make_store(tmp_path)
    run = store.create_run(
        RunCreateInput(
            project="demo",
            goal="Exercise the production planner transport seam",
            urgency="normal",
            risk="medium",
        ),
    )
    approval = store.list_approvals(status=ApprovalStatus.PENDING)[0]
    store.resolve_approval(str(approval.id), approved=True)
    return store.build_planner_context(str(run.id))


def test_scripted_transport_includes_transport_audit(tmp_path: Path) -> None:
    context = _approved_planner_context(tmp_path)
    adapter = LangGraphPlannerAdapter(
        transport=ScriptedStructuredPlannerTransport(
            [
                {
                    "kind": "action",
                    "analysis_summary": "Bounded execution is the next legal move.",
                    "confidence": "medium",
                    "selected_action": "execute_bounded_task",
                    "expected_outcome": "One bounded execution proposal should be recorded.",
                },
            ],
        ),
    )

    invocation = adapter.invoke(context)

    assert invocation.parsed_output.kind == "action"
    assert invocation.transport_audit.provider == PlannerTransportProvider.SCRIPTED
    assert invocation.transport_audit.model == "scripted-proof"
    assert invocation.transport_audit.retry_count == 0
    assert invocation.transport_audit.user_prompt_chars > 0
    assert invocation.transport_audit.system_prompt_hash != invocation.transport_audit.user_prompt_hash


class _FakeOpenAIUsage:
    def __init__(self, *, prompt_tokens: int, completion_tokens: int, total_tokens: int) -> None:
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.total_tokens = total_tokens


class _FakeOpenAIResponse:
    def __init__(self, payload: dict[str, object], *, model: str, response_id: str) -> None:
        self.id = response_id
        self.model = model
        self.usage = _FakeOpenAIUsage(prompt_tokens=111, completion_tokens=29, total_tokens=140)
        self.choices = [
            SimpleNamespace(
                message=SimpleNamespace(
                    content=json.dumps(payload),
                    refusal=None,
                ),
            ),
        ]


class _AlwaysSuccessfulFakeClient:
    def __init__(self, payload: dict[str, object], *, model: str = "gpt-4o") -> None:
        self.chat = SimpleNamespace(
            completions=SimpleNamespace(
                create=lambda **kwargs: _FakeOpenAIResponse(
                    payload,
                    model=model,
                    response_id="resp_success_1",
                ),
            ),
        )


def test_openai_transport_returns_normalized_usage_metadata() -> None:
    payload = {
        "kind": "action",
        "analysis_summary": "Bounded execution is ready.",
        "confidence": "high",
        "selected_action": "execute_bounded_task",
        "expected_outcome": "The next executor step can proceed.",
    }
    transport = OpenAIStructuredPlannerTransport(
        model="gpt-4o",
        client=_AlwaysSuccessfulFakeClient(payload),
        max_retries=0,
    )

    response = transport.invoke(
        system_prompt="system prompt",
        user_prompt="user prompt",
        output_schema={"type": "object"},
    )

    assert response.provider == PlannerTransportProvider.OPENAI
    assert response.model == "gpt-4o"
    assert response.response_id == "resp_success_1"
    assert response.retry_count == 0
    assert response.input_tokens == 111
    assert response.output_tokens == 29
    assert response.total_tokens == 140


class RateLimitError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.status_code = 429


class _RetryingFakeClient:
    def __init__(self, payload: dict[str, object], *, model: str = "gpt-4o") -> None:
        self._calls = 0

        def _create(**kwargs):
            self._calls += 1
            if self._calls == 1:
                raise RateLimitError("too many requests")
            return _FakeOpenAIResponse(payload, model=model, response_id="resp_retry_2")

        self.chat = SimpleNamespace(completions=SimpleNamespace(create=_create))


def test_openai_transport_retries_rate_limits_and_succeeds() -> None:
    payload = {
        "kind": "escalation",
        "analysis_summary": "A founder clarification is still required.",
        "confidence": "low_needs_review",
        "escalation_target": "founder",
        "help_kind": "clarification",
        "blocking_reason": "The provider recovered, but the planner still needs a bounded hint.",
        "requested_help": "Clarify whether the approval lane is still the intended next step.",
    }
    transport = OpenAIStructuredPlannerTransport(
        model="gpt-4o",
        client=_RetryingFakeClient(payload),
        max_retries=1,
        backoff_seconds=0,
    )

    response = transport.invoke(
        system_prompt="system prompt",
        user_prompt="user prompt",
        output_schema={"type": "object"},
    )

    assert response.provider == PlannerTransportProvider.OPENAI
    assert response.retry_count == 1
    assert response.response_id == "resp_retry_2"
