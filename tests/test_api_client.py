import pytest
import json
import os


def test_api_ts_file_exists():
    """Verify test/service-frontend/lib/api.ts exists."""
    assert os.path.isfile('test/service-frontend/lib/api.ts')


def test_api_ts_exports_api_function():
    """Verify api.ts exports api function."""
    with open('test/service-frontend/lib/api.ts', 'r') as f:
        content = f.read()
    assert 'async function api<T>' in content
    assert 'export { api }' in content


def test_api_ts_exports_notification_helpers():
    """Verify all notification helper functions are exported."""
    with open('test/service-frontend/lib/api.ts', 'r') as f:
        content = f.read()
    assert 'export async function listNotifications' in content
    assert 'export async function patchNotification' in content


def test_api_ts_exports_focus_helpers():
    """Verify all focus helper functions are exported."""
    with open('test/service-frontend/lib/api.ts', 'r') as f:
        content = f.read()
    assert 'export async function startFocus' in content
    assert 'export async function endFocus' in content
    assert 'export async function getCurrentFocus' in content


def test_api_ts_exports_briefing_helpers():
    """Verify all briefing helper functions are exported."""
    with open('test/service-frontend/lib/api.ts', 'r') as f:
        content = f.read()
    assert 'export async function generateBriefing' in content
    assert 'export async function getLatestBriefing' in content


def test_api_ts_exports_integration_helpers():
    """Verify all integration helper functions are exported."""
    with open('test/service-frontend/lib/api.ts', 'r') as f:
        content = f.read()
    assert 'export async function listIntegrations' in content
    assert 'export async function getSlackInstallUrl' in content


def test_api_ts_uses_api_base_env():
    """Verify api.ts uses NEXT_PUBLIC_API_BASE environment variable."""
    with open('test/service-frontend/lib/api.ts', 'r') as f:
        content = f.read()
    assert 'process.env.NEXT_PUBLIC_API_BASE' in content
    assert 'http://localhost:8000' in content


def test_api_ts_reads_bearer_token():
    """Verify api.ts reads Bearer token from localStorage."""
    with open('test/service-frontend/lib/api.ts', 'r') as f:
        content = f.read()
    assert "localStorage.getItem('cochat_token')" in content
    assert 'Bearer' in content


def test_api_ts_throws_on_non_2xx():
    """Verify api.ts throws error on non-2xx responses."""
    with open('test/service-frontend/lib/api.ts', 'r') as f:
        content = f.read()
    assert 'if (!response.ok)' in content
    assert 'throw error' in content


def test_api_ts_parses_error_json():
    """Verify api.ts parses JSON from error responses."""
    with open('test/service-frontend/lib/api.ts', 'r') as f:
        content = f.read()
    assert 'response.json()' in content
    assert 'error.data' in content


def test_sse_ts_file_exists():
    """Verify test/service-frontend/lib/sse.ts exists."""
    assert os.path.isfile('test/service-frontend/lib/sse.ts')


def test_sse_ts_exports_subscribe_notifications():
    """Verify sse.ts exports subscribeNotifications function."""
    with open('test/service-frontend/lib/sse.ts', 'r') as f:
        content = f.read()
    assert 'export' in content and 'subscribeNotifications' in content


def test_sse_ts_uses_event_source():
    """Verify sse.ts uses EventSource."""
    with open('test/service-frontend/lib/sse.ts', 'r') as f:
        content = f.read()
    assert 'EventSource' in content


def test_sse_ts_uses_notifications_stream():
    """Verify sse.ts connects to /api/v1/notifications/stream endpoint."""
    with open('test/service-frontend/lib/sse.ts', 'r') as f:
        content = f.read()
    assert '/api/v1/notifications/stream' in content


def test_sse_ts_supports_token_query_param():
    """Verify sse.ts supports token as query parameter fallback."""
    with open('test/service-frontend/lib/sse.ts', 'r') as f:
        content = f.read()
    # Check for token handling in EventSource URL construction
    assert 'token' in content.lower() or 'Bearer' in content


def test_types_ts_file_exists():
    """Verify test/service-frontend/lib/types.ts exists."""
    assert os.path.isfile('test/service-frontend/lib/types.ts')


def test_types_ts_exports_notification():
    """Verify types.ts exports Notification type."""
    with open('test/service-frontend/lib/types.ts', 'r') as f:
        content = f.read()
    assert 'export' in content and 'Notification' in content


def test_types_ts_exports_focus_session():
    """Verify types.ts exports FocusSession type."""
    with open('test/service-frontend/lib/types.ts', 'r') as f:
        content = f.read()
    assert 'export' in content and 'FocusSession' in content


def test_types_ts_exports_briefing():
    """Verify types.ts exports Briefing type."""
    with open('test/service-frontend/lib/types.ts', 'r') as f:
        content = f.read()
    assert 'export' in content and 'Briefing' in content


def test_types_ts_exports_integration():
    """Verify types.ts exports Integration type."""
    with open('test/service-frontend/lib/types.ts', 'r') as f:
        content = f.read()
    assert 'export' in content and 'Integration' in content


def test_types_ts_exports_urgency():
    """Verify types.ts exports Urgency union type."""
    with open('test/service-frontend/lib/types.ts', 'r') as f:
        content = f.read()
    assert 'Urgency' in content


def test_api_ts_imports_from_types():
    """Verify api.ts imports types from ./types."""
    with open('test/service-frontend/lib/api.ts', 'r') as f:
        content = f.read()
    assert "from './types'" in content


def test_api_ts_notification_paths_correct():
    """Verify notification endpoints use correct API paths."""
    with open('test/service-frontend/lib/api.ts', 'r') as f:
        content = f.read()
    assert '/api/v1/workspaces/' in content
    assert '/notifications' in content


def test_api_ts_focus_paths_correct():
    """Verify focus endpoints use correct API paths."""
    with open('test/service-frontend/lib/api.ts', 'r') as f:
        content = f.read()
    assert '/focus/start' in content
    assert '/focus/end' in content
    assert '/focus/current' in content


def test_api_ts_briefing_paths_correct():
    """Verify briefing endpoints use correct API paths."""
    with open('test/service-frontend/lib/api.ts', 'r') as f:
        content = f.read()
    assert '/briefings/generate' in content
    assert '/briefings/latest' in content


def test_api_ts_integration_paths_correct():
    """Verify integration endpoints use correct API paths."""
    with open('test/service-frontend/lib/api.ts', 'r') as f:
        content = f.read()
    assert '/integrations' in content
    assert '/slack/install-url' in content


def test_api_ts_proper_http_methods():
    """Verify api.ts uses proper HTTP methods for endpoints."""
    with open('test/service-frontend/lib/api.ts', 'r') as f:
        content = f.read()
    assert "'POST'" in content or '"POST"' in content
    assert "'PATCH'" in content or '"PATCH"' in content


def test_types_ts_has_interface_definitions():
    """Verify types.ts contains interface definitions."""
    with open('test/service-frontend/lib/types.ts', 'r') as f:
        content = f.read()
    assert 'interface' in content or 'type' in content
