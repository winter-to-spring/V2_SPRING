"""Test that dashboard page and notification card components are created with expected content."""
import os
import re


def test_dashboard_page_exists():
    """Verify dashboard page component file exists."""
    path = "test/service-frontend/app/dashboard/page.tsx"
    assert os.path.isfile(path), f"File {path} does not exist"


def test_dashboard_page_is_client_component():
    """Verify dashboard page is marked as client component."""
    path = "test/service-frontend/app/dashboard/page.tsx"
    with open(path, "r") as f:
        content = f.read()
    assert "'use client'" in content, "Missing 'use client' directive"


def test_dashboard_page_imports_api_functions():
    """Verify dashboard imports listNotifications, subscribeToNotifications, patchNotification."""
    path = "test/service-frontend/app/dashboard/page.tsx"
    with open(path, "r") as f:
        content = f.read()
    assert "listNotifications" in content, "Missing listNotifications import"
    assert "subscribeToNotifications" in content, "Missing subscribeToNotifications import"
    assert "patchNotification" in content, "Missing patchNotification import"


def test_dashboard_page_uses_notification_card():
    """Verify dashboard imports and renders NotificationCard."""
    path = "test/service-frontend/app/dashboard/page.tsx"
    with open(path, "r") as f:
        content = f.read()
    assert "NotificationCard" in content, "Missing NotificationCard import"
    assert "<NotificationCard" in content, "NotificationCard not rendered"


def test_dashboard_page_groups_by_urgency():
    """Verify dashboard groups notifications by urgency."""
    path = "test/service-frontend/app/dashboard/page.tsx"
    with open(path, "r") as f:
        content = f.read()
    urgency_levels = ["Critical", "High", "Medium", "Low"]
    for level in urgency_levels:
        assert level in content, f"Missing urgency level: {level}"
    assert "groupedByUrgency" in content, "Missing groupedByUrgency logic"


def test_dashboard_page_subscribes_to_sse():
    """Verify dashboard subscribes to SSE on mount."""
    path = "test/service-frontend/app/dashboard/page.tsx"
    with open(path, "r") as f:
        content = f.read()
    assert "subscribeToNotifications" in content, "Missing SSE subscription"
    assert "useEffect" in content, "Missing useEffect hook"


def test_dashboard_page_prepends_new_notifications():
    """Verify new notifications are prepended to list."""
    path = "test/service-frontend/app/dashboard/page.tsx"
    with open(path, "r") as f:
        content = f.read()
    # Check for prepend pattern: [newNotification, ...prev]
    assert "[newNotification, ...prev]" in content, "New notifications not prepended"


def test_dashboard_page_shows_loading_state():
    """Verify dashboard shows loading skeletons."""
    path = "test/service-frontend/app/dashboard/page.tsx"
    with open(path, "r") as f:
        content = f.read()
    assert "loading" in content.lower(), "Missing loading state"
    assert "NotificationCardSkeleton" in content, "Missing skeleton component"


def test_dashboard_page_shows_empty_state():
    """Verify dashboard shows empty state message."""
    path = "test/service-frontend/app/dashboard/page.tsx"
    with open(path, "r") as f:
        content = f.read()
    assert "All caught up" in content or "no notifications" in content.lower(), "Missing empty state message"


def test_dashboard_page_spacing_matches_figma():
    """Verify dashboard uses correct Figma spacing."""
    path = "test/service-frontend/app/dashboard/page.tsx"
    with open(path, "r") as f:
        content = f.read()
    assert "p-6" in content, "Missing p-6 padding"
    assert "max-w-6xl" in content, "Missing max-w-6xl constraint"
    assert "mx-auto" in content, "Missing mx-auto centering"
    assert "gap-4" in content, "Missing gap-4 spacing"


def test_dashboard_page_handles_dismiss():
    """Verify dashboard dismisses notifications."""
    path = "test/service-frontend/app/dashboard/page.tsx"
    with open(path, "r") as f:
        content = f.read()
    assert "handleDismiss" in content, "Missing handleDismiss handler"
    assert "onDismiss={handleDismiss}" in content, "NotificationCard not passed onDismiss"


def test_notification_card_exists():
    """Verify notification card component file exists."""
    path = "test/service-frontend/components/notification-card.tsx"
    assert os.path.isfile(path), f"File {path} does not exist"


def test_notification_card_accepts_notification_prop():
    """Verify notification card accepts Notification prop."""
    path = "test/service-frontend/components/notification-card.tsx"
    with open(path, "r") as f:
        content = f.read()
    assert "Notification" in content, "Missing Notification type"
    assert "notification" in content.lower(), "Missing notification prop"


def test_notification_card_imports_card():
    """Verify notification card imports Card component."""
    path = "test/service-frontend/components/notification-card.tsx"
    with open(path, "r") as f:
        content = f.read()
    assert "Card" in content, "Missing Card import"


def test_notification_card_renders_triage_badge():
    """Verify notification card renders TriageBadge."""
    path = "test/service-frontend/components/notification-card.tsx"
    with open(path, "r") as f:
        content = f.read()
    assert "TriageBadge" in content, "Missing TriageBadge component"


def test_notification_card_displays_all_fields():
    """Verify notification card displays all required fields."""
    path = "test/service-frontend/components/notification-card.tsx"
    with open(path, "r") as f:
        content = f.read()
    required_fields = ["channel_name", "sender_name", "summary"]
    for field in required_fields:
        assert field in content, f"Missing field: {field}"


def test_notification_card_shows_relative_timestamp():
    """Verify notification card shows relative timestamp."""
    path = "test/service-frontend/components/notification-card.tsx"
    with open(path, "r") as f:
        content = f.read()
    assert "timestamp" in content.lower() or "date" in content.lower(), "Missing timestamp display"


def test_notification_card_has_dismiss_button():
    """Verify notification card has dismiss button."""
    path = "test/service-frontend/components/notification-card.tsx"
    with open(path, "r") as f:
        content = f.read()
    assert "Dismiss" in content, "Missing Dismiss button"
    assert "Button" in content, "Missing Button component"


def test_notification_card_calls_patch_on_dismiss():
    """Verify notification card calls patchNotification on dismiss."""
    path = "test/service-frontend/components/notification-card.tsx"
    with open(path, "r") as f:
        content = f.read()
    assert "patchNotification" in content, "Missing patchNotification call"
    assert "dismissed" in content, "Missing dismissed state"


def test_notification_card_is_client_component():
    """Verify notification card is client component."""
    path = "test/service-frontend/components/notification-card.tsx"
    with open(path, "r") as f:
        content = f.read()
    assert "'use client'" in content, "Missing 'use client' directive"


def test_notification_card_has_on_dismiss_handler():
    """Verify notification card accepts onDismiss handler prop."""
    path = "test/service-frontend/components/notification-card.tsx"
    with open(path, "r") as f:
        content = f.read()
    assert "onDismiss" in content, "Missing onDismiss prop"
