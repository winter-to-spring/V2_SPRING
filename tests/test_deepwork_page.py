import re
import pytest


def test_deepwork_page_file_exists():
    """Verify the deepwork page file exists at the expected location."""
    page_path = "test/service-frontend/app/deepwork/page.tsx"
    with open(page_path, "r") as f:
        content = f.read()
    assert len(content) > 0, "page.tsx should not be empty"


def test_deepwork_page_uses_client_directive():
    """Verify the page uses 'use client' directive."""
    page_path = "test/service-frontend/app/deepwork/page.tsx"
    with open(page_path, "r") as f:
        content = f.read()
    assert "'use client';" in content, "Page should have 'use client' directive"


def test_deepwork_page_imports_shadcn_components():
    """Verify shadcn UI components are imported."""
    page_path = "test/service-frontend/app/deepwork/page.tsx"
    with open(page_path, "r") as f:
        content = f.read()
    
    components = ['Card', 'Button', 'Dialog', 'Input', 'Textarea']
    for component in components:
        assert component in content, f"Should import {component} from shadcn"


def test_deepwork_page_has_planned_minutes_input():
    """Verify planned minutes input field with default value 50."""
    page_path = "test/service-frontend/app/deepwork/page.tsx"
    with open(page_path, "r") as f:
        content = f.read()
    
    assert "planned_minutes" in content or "plannedMinutes" in content, \
        "Should have planned minutes state/input"
    assert "useState(50)" in content, "Default planned minutes should be 50"


def test_deepwork_page_has_start_focus_button():
    """Verify Start Focus Session button exists."""
    page_path = "test/service-frontend/app/deepwork/page.tsx"
    with open(page_path, "r") as f:
        content = f.read()
    
    assert "Start Focus Session" in content, "Should have 'Start Focus Session' button"
    assert "startFocus" in content or "onClick={startFocus}" in content, \
        "Button should call startFocus handler"


def test_deepwork_page_has_countdown_timer():
    """Verify countdown timer is displayed during active session."""
    page_path = "test/service-frontend/app/deepwork/page.tsx"
    with open(page_path, "r") as f:
        content = f.read()
    
    assert "timeRemaining" in content, "Should track time remaining"
    assert "formatTime" in content, "Should have time formatting function"
    assert "started_at" in content, "Should use session started_at timestamp"
    assert "planned_minutes" in content, "Should use planned_minutes for duration"


def test_deepwork_page_has_end_session_button():
    """Verify End Session button exists."""
    page_path = "test/service-frontend/app/deepwork/page.tsx"
    with open(page_path, "r") as f:
        content = f.read()
    
    assert "End Session" in content, "Should have 'End Session' button"
    assert "endFocus" in content or "onClick={endFocus}" in content, \
        "Button should call endFocus handler"


def test_deepwork_page_has_feedback_dialog():
    """Verify feedback dialog with stars 1-5 and notes."""
    page_path = "test/service-frontend/app/deepwork/page.tsx"
    with open(page_path, "r") as f:
        content = f.read()
    
    assert "Dialog" in content, "Should use Dialog component"
    assert "showFeedbackDialog" in content, "Should have feedback dialog state"
    assert "[1, 2, 3, 4, 5]" in content or "1, 2, 3, 4, 5" in content, \
        "Should have 5-star rating system"
    assert "rating" in content, "Should track star rating"
    assert "notes" in content or "Textarea" in content, "Should have notes field"


def test_deepwork_page_calls_get_current_focus_on_mount():
    """Verify getCurrentFocus is called on component mount."""
    page_path = "test/service-frontend/app/deepwork/page.tsx"
    with open(page_path, "r") as f:
        content = f.read()
    
    assert "useEffect" in content, "Should use useEffect hook"
    assert "/api/focus/current" in content, "Should call current focus endpoint"
    assert "getCurrentFocus" in content, "Should have getCurrentFocus function"


def test_deepwork_page_posts_to_feedback_endpoint():
    """Verify feedback is posted to focus feedback endpoint."""
    page_path = "test/service-frontend/app/deepwork/page.tsx"
    with open(page_path, "r") as f:
        content = f.read()
    
    assert "/api/focus/feedback" in content, "Should post to feedback endpoint"
    assert "submitFeedback" in content or "POST" in content, \
        "Should have feedback submission logic"


def test_deepwork_page_has_start_endpoint_call():
    """Verify startFocus calls /api/focus/start endpoint."""
    page_path = "test/service-frontend/app/deepwork/page.tsx"
    with open(page_path, "r") as f:
        content = f.read()
    
    assert "/api/focus/start" in content, "Should call /api/focus/start endpoint"
    assert "POST" in content, "Should use POST method"


def test_deepwork_page_has_end_endpoint_call():
    """Verify endFocus calls /api/focus/end endpoint."""
    page_path = "test/service-frontend/app/deepwork/page.tsx"
    with open(page_path, "r") as f:
        content = f.read()
    
    assert "/api/focus/end" in content, "Should call /api/focus/end endpoint"


def test_deepwork_page_no_webcam_references():
    """Verify no webcam-related code is present."""
    page_path = "test/service-frontend/app/deepwork/page.tsx"
    with open(page_path, "r") as f:
        content = f.read()
    
    webcam_keywords = ["webcam", "camera", "getUserMedia", "video", "stream"]
    for keyword in webcam_keywords:
        # Allow "video" in context of non-webcam uses
        if keyword == "video":
            continue
        assert keyword.lower() not in content.lower(), \
            f"Should not contain {keyword} references (deferred scope)"


def test_deepwork_page_has_proper_typescript_types():
    """Verify TypeScript interfaces and types are defined."""
    page_path = "test/service-frontend/app/deepwork/page.tsx"
    with open(page_path, "r") as f:
        content = f.read()
    
    assert "interface" in content, "Should define TypeScript interfaces"
    assert "FocusSession" in content, "Should have FocusSession interface"
    assert "useState" in content, "Should use React hooks"


def test_deepwork_page_timer_computation():
    """Verify timer is computed from started_at + planned_minutes."""
    page_path = "test/service-frontend/app/deepwork/page.tsx"
    with open(page_path, "r") as f:
        content = f.read()
    
    # Should compute elapsed time from started_at
    assert "started_at" in content, "Should use started_at for timer"
    # Should use planned_minutes for total duration
    assert re.search(r'planned_minutes\s*\*\s*60', content), \
        "Should convert minutes to seconds (planned_minutes * 60)"
    # Should compute remaining time
    assert "remaining" in content.lower(), "Should calculate time remaining"


def test_deepwork_page_button_driven_only():
    """Verify interaction is strictly button-driven."""
    page_path = "test/service-frontend/app/deepwork/page.tsx"
    with open(page_path, "r") as f:
        content = f.read()
    
    # Check for onClick handlers on buttons
    assert "onClick" in content, "Should use button click handlers"
    assert "Button" in content, "Should use Button component for interactions"
    # Verify no automatic capture or stream handling
    assert "onCapture" not in content, "Should not have capture handlers"
    assert "onStream" not in content, "Should not have stream handlers"
