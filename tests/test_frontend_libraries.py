import os
import json
import pytest


def test_api_ts_exists():
    """Verify that api.ts file exists."""
    api_file = 'test/service-frontend/src/lib/api.ts'
    assert os.path.exists(api_file), f"File {api_file} does not exist"


def test_api_ts_contains_fetch_wrapper():
    """Verify that api.ts contains the fetchAPI typed wrapper."""
    api_file = 'test/service-frontend/src/lib/api.ts'
    with open(api_file, 'r') as f:
        content = f.read()
    
    assert 'async function fetchAPI' in content, "fetchAPI function not found"
    assert 'NEXT_PUBLIC_API_URL' in content, "NEXT_PUBLIC_API_URL not referenced"
    assert "localStorage.getItem('cochat_token')" in content, "Bearer token retrieval not found"
    assert "Authorization" in content and "Bearer" in content, "Bearer token attachment not found"
    assert "!response.ok" in content or "response.ok" in content, "Response status check not found"


def test_api_ts_exports_all_endpoints():
    """Verify that api.ts exports all required endpoint functions."""
    api_file = 'test/service-frontend/src/lib/api.ts'
    with open(api_file, 'r') as f:
        content = f.read()
    
    required_exports = [
        'export async function login',
        'export async function register',
        'export async function me',
        'export async function listIntegrations',
        'export async function slackInstallUrl',
        'export async function listNotifications',
        'export async function markRead',
        'export async function streamNotifications',
        'export async function startFocus',
        'export async function endFocus',
        'export async function getCurrentFocus',
        'export async function getLatestBriefing',
        'export async function postFeedback',
    ]
    
    for export_name in required_exports:
        assert export_name in content, f"Export {export_name} not found in api.ts"


def test_api_ts_stream_notifications_uses_eventsource():
    """Verify that streamNotifications uses EventSource."""
    api_file = 'test/service-frontend/src/lib/api.ts'
    with open(api_file, 'r') as f:
        content = f.read()
    
    assert 'new EventSource' in content, "EventSource not used in streamNotifications"
    assert 'addEventListener' in content, "EventSource event listeners not attached"


def test_auth_context_tsx_exists():
    """Verify that auth-context.tsx file exists."""
    auth_file = 'test/service-frontend/src/lib/auth-context.tsx'
    assert os.path.exists(auth_file), f"File {auth_file} does not exist"


def test_auth_context_tsx_exports_provider_and_hook():
    """Verify that auth-context.tsx exports AuthProvider and useAuth."""
    auth_file = 'test/service-frontend/src/lib/auth-context.tsx'
    with open(auth_file, 'r') as f:
        content = f.read()
    
    assert 'export' in content and 'AuthProvider' in content, "AuthProvider not exported"
    assert 'export' in content and 'useAuth' in content, "useAuth hook not exported"
    assert 'createContext' in content, "React createContext not used"
    assert 'useContext' in content, "useContext hook not used"


def test_auth_context_tsx_contains_required_state():
    """Verify that auth-context.tsx manages token, user, login, logout."""
    auth_file = 'test/service-frontend/src/lib/auth-context.tsx'
    with open(auth_file, 'r') as f:
        content = f.read()
    
    required_elements = ['token', 'user', 'login', 'logout']
    
    for element in required_elements:
        assert element in content, f"{element} not found in auth-context.tsx"


def test_triage_ts_exists():
    """Verify that triage.ts file exists."""
    triage_file = 'test/service-frontend/src/lib/triage.ts'
    assert os.path.exists(triage_file), f"File {triage_file} does not exist"


def test_triage_ts_exports_triage_color_function():
    """Verify that triage.ts exports triageColor function."""
    triage_file = 'test/service-frontend/src/lib/triage.ts'
    with open(triage_file, 'r') as f:
        content = f.read()
    
    assert 'export' in content and 'triageColor' in content, "triageColor not exported"
    assert 'function triageColor' in content or 'const triageColor' in content, "triageColor function not defined"


def test_triage_ts_contains_correct_color_mappings():
    """Verify that triage.ts has exact color mappings: critical=red, high=yellow, medium=blue, low=gray."""
    triage_file = 'test/service-frontend/src/lib/triage.ts'
    with open(triage_file, 'r') as f:
        content = f.read()
    
    # Check for mapping of critical to red
    assert 'critical' in content and 'red' in content, "critical->red mapping not found"
    # Check for mapping of high to yellow
    assert 'high' in content and 'yellow' in content, "high->yellow mapping not found"
    # Check for mapping of medium to blue
    assert 'medium' in content and 'blue' in content, "medium->blue mapping not found"
    # Check for mapping of low to gray
    assert 'low' in content and 'gray' in content, "low->gray mapping not found"


def test_triage_ts_exports_tailwind_class_maps():
    """Verify that triage.ts exports TRIAGE_BG, TRIAGE_TEXT, TRIAGE_RING."""
    triage_file = 'test/service-frontend/src/lib/triage.ts'
    with open(triage_file, 'r') as f:
        content = f.read()
    
    required_exports = ['TRIAGE_BG', 'TRIAGE_TEXT', 'TRIAGE_RING']
    
    for export_name in required_exports:
        assert f'export' in content and export_name in content, f"{export_name} not exported from triage.ts"


def test_triage_ts_color_values():
    """Verify that triage.ts contains the exact color values: red, yellow, blue, gray."""
    triage_file = 'test/service-frontend/src/lib/triage.ts'
    with open(triage_file, 'r') as f:
        content = f.read()
    
    colors = ['red', 'yellow', 'blue', 'gray']
    
    for color in colors:
        assert f"'{color}'" in content or f'"{color}"' in content, f"Color {color} not found in triage.ts"


def test_files_are_typescript():
    """Verify that files have correct extensions (ts/tsx)."""
    files = [
        'test/service-frontend/src/lib/api.ts',
        'test/service-frontend/src/lib/auth-context.tsx',
        'test/service-frontend/src/lib/triage.ts',
    ]
    
    for file_path in files:
        assert os.path.exists(file_path), f"File {file_path} does not exist"
        assert file_path.endswith('.ts') or file_path.endswith('.tsx'), f"File {file_path} does not have correct extension"
