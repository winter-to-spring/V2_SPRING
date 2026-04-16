from __future__ import annotations

import json
from typing import Any, Protocol, TypedDict

from langgraph.graph import END, START, StateGraph
from pydantic import ValidationError

from v2_spring.domain.planner_adapter import (
    PLANNER_ADAPTER_OUTPUT_ADAPTER,
    PlannerAdapterOutput,
    PlannerContextWindow,
)
from v2_spring.planner.proposals import PlannerAdapterFormatError


class StructuredPlannerTransport(Protocol):
    """Transport contract for any bounded structured planner backend."""

    def invoke(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        output_schema: dict[str, Any],
    ) -> Any: ...


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
    ) -> Any:
        if not self._responses:
            if self._fallback_response is None:
                raise RuntimeError("No scripted planner responses remain for this invocation.")
            return self._fallback_response
        return self._responses.pop(0)


class PlannerGraphState(TypedDict, total=False):
    context: PlannerContextWindow
    raw_response: Any
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
    ) -> None:
        self._transport = transport
        self._max_format_retries = max_format_retries
        self._compiled = self._build_graph().compile()

    def invoke(self, context: PlannerContextWindow) -> tuple[PlannerAdapterOutput, int]:
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
            )
        return parsed, state.get("format_failures", 0)

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
        raw_response = self._transport.invoke(
            system_prompt=self._build_system_prompt(),
            user_prompt=self._build_user_prompt(context, parse_errors=state.get("parse_errors", [])),
            output_schema=PLANNER_ADAPTER_OUTPUT_ADAPTER.json_schema(),
        )
        return {"raw_response": raw_response}

    def _parse_output(self, state: PlannerGraphState) -> PlannerGraphState:
        raw_response = state.get("raw_response")
        normalized = raw_response
        if isinstance(raw_response, str):
            normalized = json.loads(raw_response)
        try:
            parsed = PLANNER_ADAPTER_OUTPUT_ADAPTER.validate_python(normalized)
        except (ValidationError, json.JSONDecodeError) as exc:
            return {
                "format_failures": state.get("format_failures", 0) + 1,
                "parse_errors": [*state.get("parse_errors", []), str(exc)],
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
            "Return only schema-valid structured output. "
            "Prefer a legal action proposal when the context shows a safe next move. "
            "Use escalation only when every available legal action is blocked by a clear founder-facing blocker. "
            "Do not fabricate missing state. "
            "Summarize your reasoning in analysis_summary rather than emitting hidden chain-of-thought."
        )

    @staticmethod
    def _build_user_prompt(
        context: PlannerContextWindow,
        *,
        parse_errors: list[str],
    ) -> str:
        payload = context.model_dump(mode="json")
        if parse_errors:
            payload["adapter_feedback"] = {
                "previous_parse_errors": parse_errors[-2:],
                "instruction": "Return a schema-valid response that matches the discriminator and field requirements.",
            }
        return json.dumps(payload, ensure_ascii=False, indent=2)
