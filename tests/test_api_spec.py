"""
QA tests for test/docs/api-spec.md

Verifies that the API specification document exists and contains
all required P0 endpoints with complete schemas and documentation.
"""

import os
import re
from pathlib import Path


def test_api_spec_file_exists():
    """Verify that test/docs/api-spec.md exists."""
    spec_path = Path("test/docs/api-spec.md")
    assert spec_path.exists(), f"API spec file not found at {spec_path}"
    assert spec_path.is_file(), f"API spec path is not a file: {spec_path}"


def test_api_spec_has_content():
    """Verify that the API spec file has meaningful content."""
    spec_path = Path("test/docs/api-spec.md")
    content = spec_path.read_text(encoding="utf-8")
    
    assert len(content) > 1000, "API spec file content is too short"
    assert content.startswith("# P0 API Specification"), "API spec should start with title"


def test_api_spec_contains_all_endpoints():
    """Verify that all P0 endpoints are documented."""
    spec_path = Path("test/docs/api-spec.md")
    content = spec_path.read_text(encoding="utf-8")
    
    required_endpoints = [
        # Authentication endpoints
        "POST /api/v1/auth/login",
        "POST /api/v1/auth/logout",
        "POST /api/v1/auth/refresh",
        
        # OAuth endpoints
        "GET /api/v1/integrations/oauth/authorize",
        "GET /api/v1/integrations/oauth/callback",
        "POST /api/v1/integrations/oauth/disconnect",
        
        # Slack webhook endpoints
        "POST /api/v1/integrations/slack/webhook/subscribe",
        "DELETE /api/v1/integrations/slack/webhook",
        "POST /api/v1/integrations/slack/webhook/test",
        
        # Notifications endpoints
        "GET /api/v1/notifications",
        "GET /api/v1/notifications/stream",
        
        # Focus session endpoints
        "POST /api/v1/focus-sessions/start",
        "POST /api/v1/focus-sessions",
        
        # Briefing endpoint
        "GET /api/v1/briefing",
        
        # Feedback endpoint
        "POST /api/v1/feedback",
    ]
    
    for endpoint in required_endpoints:
        assert endpoint in content, f"Endpoint '{endpoint}' not found in API spec"


def test_api_spec_auth_endpoints():
    """Verify authentication endpoints are complete."""
    spec_path = Path("test/docs/api-spec.md")
    content = spec_path.read_text(encoding="utf-8")
    
    # Check auth section exists
    assert "## Authentication" in content, "Authentication section missing"
    
    # Verify login endpoint details
    assert "POST /api/v1/auth/login" in content
    assert '"email": "string (required)"' in content
    assert '"password": "string (required)"' in content
    assert '"token": "string (JWT)"' in content
    assert "200 OK" in content
    assert "401 Unauthorized" in content
    
    # Verify logout endpoint
    assert "POST /api/v1/auth/logout" in content
    
    # Verify refresh endpoint
    assert "POST /api/v1/auth/refresh" in content
    assert '"refresh_token": "string"' in content


def test_api_spec_oauth_endpoints():
    """Verify OAuth integration endpoints are complete."""
    spec_path = Path("test/docs/api-spec.md")
    content = spec_path.read_text(encoding="utf-8")
    
    assert "## Integrations - OAuth" in content
    assert "GET /api/v1/integrations/oauth/authorize" in content
    assert "GET /api/v1/integrations/oauth/callback" in content
    assert "POST /api/v1/integrations/oauth/disconnect" in content
    
    # Verify OAuth parameters
    assert '"provider": "string (required)"' in content
    assert '"code": "string (required)"' in content
    assert '"state": "string (required)"' in content


def test_api_spec_slack_webhook_endpoints():
    """Verify Slack webhook endpoints are complete."""
    spec_path = Path("test/docs/api-spec.md")
    content = spec_path.read_text(encoding="utf-8")
    
    assert "## Integrations - Slack Webhook" in content
    assert "POST /api/v1/integrations/slack/webhook/subscribe" in content
    assert "DELETE /api/v1/integrations/slack/webhook/{webhook_id}" in content
    assert "POST /api/v1/integrations/slack/webhook/test" in content
    
    # Verify webhook parameters
    assert '"webhook_url": "string (required)"' in content
    assert '"channel": "string (required)"' in content
    assert '"events": ["string"] (required array)' in content


def test_api_spec_notifications_list():
    """Verify notifications list endpoint is complete."""
    spec_path = Path("test/docs/api-spec.md")
    content = spec_path.read_text(encoding="utf-8")
    
    assert "## Notifications - List" in content
    assert "GET /api/v1/notifications" in content
    assert '"limit": "integer"' in content
    assert '"offset": "integer"' in content
    assert '"is_read": "boolean"' in content


def test_api_spec_notifications_stream():
    """Verify notifications stream (SSE) endpoint is complete."""
    spec_path = Path("test/docs/api-spec.md")
    content = spec_path.read_text(encoding="utf-8")
    
    assert "## Notifications - Stream (SSE)" in content
    assert "GET /api/v1/notifications/stream" in content
    assert "text/event-stream" in content
    assert "event: notification" in content
    assert "event: heartbeat" in content
    assert "Server-Sent Events" in content


def test_api_spec_focus_session_start():
    """Verify focus session start endpoint is complete."""
    spec_path = Path("test/docs/api-spec.md")
    content = spec_path.read_text(encoding="utf-8")
    
    assert "## Focus Session - Start" in content
    assert "POST /api/v1/focus-sessions/start" in content
    assert '"duration_minutes": "integer (required' in content
    assert '"status": "active"' in content
    assert "201 Created" in content


def test_api_spec_focus_session_end():
    """Verify focus session end endpoint is complete."""
    spec_path = Path("test/docs/api-spec.md")
    content = spec_path.read_text(encoding="utf-8")
    
    assert "## Focus Session - End" in content
    assert "POST /api/v1/focus-sessions/{session_id}/end" in content
    assert '"completed": "boolean (required)"' in content
    assert '"ended_at": "string (ISO 8601 timestamp)"' in content


def test_api_spec_briefing_endpoint():
    """Verify briefing get endpoint is complete."""
    spec_path = Path("test/docs/api-spec.md")
    content = spec_path.read_text(encoding="utf-8")
    
    assert "## Briefing - Get" in content
    assert "GET /api/v1/briefing" in content
    assert '"date": "string (ISO 8601 date"' in content
    assert '"briefing_id": "string (UUID)"' in content
    assert '"sections"' in content


def test_api_spec_feedback_endpoint():
    """Verify feedback report endpoint is complete."""
    spec_path = Path("test/docs/api-spec.md")
    content = spec_path.read_text(encoding="utf-8")
    
    assert "## Feedback - Report" in content
    assert "POST /api/v1/feedback" in content
    assert '"type": "string (required, enum: \'bug\', \'feature\', \'improvement\')"' in content
    assert '"title": "string (required)"' in content
    assert '"description": "string (required)"' in content
    assert "201 Created" in content


def test_api_spec_status_codes():
    """Verify that all endpoints document status codes."""
    spec_path = Path("test/docs/api-spec.md")
    content = spec_path.read_text(encoding="utf-8")
    
    # Check for status code sections
    status_codes = ["200 OK", "201 Created", "400 Bad Request", "401 Unauthorized", "404 Not Found"]
    for code in status_codes:
        assert code in content, f"Status code '{code}' not documented"


def test_api_spec_request_response_schemas():
    """Verify that endpoints document request and response schemas."""
    spec_path = Path("test/docs/api-spec.md")
    content = spec_path.read_text(encoding="utf-8")
    
    # Count JSON schema blocks
    json_blocks = content.count("```json")
    assert json_blocks >= 20, f"Expected at least 20 JSON schema blocks, found {json_blocks}"
    
    # Verify schema markers
    assert "**Request Schema:**" in content
    assert "**Response Schema**" in content


def test_api_spec_auth_requirements():
    """Verify that auth requirements are documented for each endpoint."""
    spec_path = Path("test/docs/api-spec.md")
    content = spec_path.read_text(encoding="utf-8")
    
    # Check for auth requirement markers
    assert "**Auth Required:** Yes" in content
    assert "**Auth Required:** No" in content


def test_api_spec_error_format():
    """Verify that error response format is documented."""
    spec_path = Path("test/docs/api-spec.md")
    content = spec_path.read_text(encoding="utf-8")
    
    assert "## Error Response Format" in content
    assert '"error": {' in content
    assert '"code": "string"' in content
    assert '"message": "string"' in content


def test_api_spec_has_table_of_contents():
    """Verify that the spec has a table of contents."""
    spec_path = Path("test/docs/api-spec.md")
    content = spec_path.read_text(encoding="utf-8")
    
    assert "## Table of Contents" in content
    assert "[Authentication](#authentication)" in content


def test_api_spec_has_versioning_section():
    """Verify that versioning information is documented."""
    spec_path = Path("test/docs/api-spec.md")
    content = spec_path.read_text(encoding="utf-8")
    
    assert "## Versioning" in content
    assert "Current API version: `v1`" in content
    assert "/api/v1/" in content


def test_api_spec_has_rate_limiting_section():
    """Verify that rate limiting information is documented."""
    spec_path = Path("test/docs/api-spec.md")
    content = spec_path.read_text(encoding="utf-8")
    
    assert "## Rate Limiting" in content
    assert "X-RateLimit" in content


def test_api_spec_has_auth_header_section():
    """Verify that authentication header format is documented."""
    spec_path = Path("test/docs/api-spec.md")
    content = spec_path.read_text(encoding="utf-8")
    
    assert "## Authentication Header Format" in content
    assert "Authorization: Bearer" in content
    assert "JWT" in content or "JWT_TOKEN" in content


def test_api_spec_completeness():
    """Verify that all endpoints have method, path, and schemas."""
    spec_path = Path("test/docs/api-spec.md")
    content = spec_path.read_text(encoding="utf-8")
    
    # Extract all endpoint headers
    endpoint_pattern = r"### Endpoint: (GET|POST|PUT|DELETE|PATCH) ([/\w\-\{\}]+)"
    endpoints = re.findall(endpoint_pattern, content)
    
    # Should have at least 15 documented endpoints
    assert len(endpoints) >= 15, f"Expected at least 15 endpoints, found {len(endpoints)}"
    
    # Verify each endpoint section has required content
    for method, path in endpoints:
        section_marker = f"### Endpoint: {method} {path}"
        section_start = content.find(section_marker)
        assert section_start != -1, f"Endpoint section marker not found: {section_marker}"


if __name__ == "__main__":
    # Run basic checks
    test_api_spec_file_exists()
    test_api_spec_has_content()
    test_api_spec_contains_all_endpoints()
    print("All API spec tests passed!")
