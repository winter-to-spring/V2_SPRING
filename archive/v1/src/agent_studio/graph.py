from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from agent_studio.state import AgentStudioState


def manager_node(state: AgentStudioState) -> AgentStudioState:
    next_state = dict(state)
    next_state["current_owner"] = "manager"
    next_state["current_phase"] = "requirements_drafting"
    next_state["status"] = "in_progress"
    next_state["last_action"] = "Manager routed the request to the PM stage."
    return next_state


def pm_node(state: AgentStudioState) -> AgentStudioState:
    next_state = dict(state)
    next_state["current_owner"] = "pm"
    next_state["prd_path"] = "docs/PRD.md"
    next_state["current_phase"] = "planning"
    next_state["last_action"] = "PM prepared the first PRD draft."
    return next_state


def builder_node(state: AgentStudioState) -> AgentStudioState:
    next_state = dict(state)
    next_state["current_owner"] = "builder"
    next_state["roadmap_path"] = "docs/ROADMAP.md"
    next_state["current_phase"] = "implementation"
    next_state["last_action"] = "Builder prepared the implementation plan."
    return next_state


def qa_node(state: AgentStudioState) -> AgentStudioState:
    next_state = dict(state)
    next_state["current_owner"] = "qa"
    next_state["test_report_path"] = "docs/TEST_REPORT.md"
    next_state["lint"] = "unknown"
    next_state["typecheck"] = "unknown"
    next_state["unit"] = "unknown"
    next_state["module_smoke"] = "unknown"
    next_state["current_phase"] = "completed"
    next_state["status"] = "completed"
    next_state["last_action"] = "QA recorded the module verification state."
    return next_state


def build_graph():
    workflow = StateGraph(AgentStudioState)

    workflow.add_node("manager", manager_node)
    workflow.add_node("pm", pm_node)
    workflow.add_node("builder", builder_node)
    workflow.add_node("qa", qa_node)

    workflow.add_edge(START, "manager")
    workflow.add_edge("manager", "pm")
    workflow.add_edge("pm", "builder")
    workflow.add_edge("builder", "qa")
    workflow.add_edge("qa", END)

    return workflow.compile()
