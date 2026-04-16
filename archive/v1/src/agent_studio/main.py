from __future__ import annotations

from pprint import pprint

from dotenv import load_dotenv

from agent_studio.config import load_settings
from agent_studio.graph import build_graph


def main() -> None:
    load_dotenv()
    settings = load_settings()
    app = build_graph()

    initial_state = {
        "request_id": "local-demo-001",
        "goal": "Create the first Agent Studio workflow skeleton.",
        "current_phase": "inbox",
        "current_owner": "founder",
        "status": "created",
        "prd_path": "",
        "roadmap_path": "",
        "test_report_path": "",
        "lint": "unknown",
        "typecheck": "unknown",
        "unit": "unknown",
        "module_smoke": "unknown",
        "requirements_approved": False,
        "release_approved": False,
        "last_action": "Request created.",
        "blocker": "",
    }

    print(f"[agent-studio] env={settings.app_env} tz={settings.timezone}")
    result = app.invoke(initial_state)
    pprint(result)


if __name__ == "__main__":
    main()
