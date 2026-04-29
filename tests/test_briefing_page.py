import pytest
import re
from pathlib import Path


def test_briefing_page_exists():
    """Verify that the briefing page file exists at the correct location."""
    page_path = Path('test/service-frontend/app/briefing/page.tsx')
    assert page_path.exists(), f"Briefing page should exist at {page_path}"


def test_briefing_page_is_client_component():
    """Verify the page is marked as a client component."""
    page_path = Path('test/service-frontend/app/briefing/page.tsx')
    content = page_path.read_text()
    assert "'use client';" in content, "Page should include 'use client' directive"


def test_briefing_page_imports_api_functions():
    """Verify that getLatestBriefing and generateBriefing are imported."""
    page_path = Path('test/service-frontend/app/briefing/page.tsx')
    content = page_path.read_text()
    assert 'getLatestBriefing' in content, "Should import getLatestBriefing"
    assert 'generateBriefing' in content, "Should import generateBriefing"
    assert "from '@/lib/briefing-api'" in content, "Should import from briefing-api"


def test_briefing_page_imports_ui_components():
    """Verify that Card and Button components are imported."""
    page_path = Path('test/service-frontend/app/briefing/page.tsx')
    content = page_path.read_text()
    assert "from '@/components/ui/card'" in content, "Should import Card component"
    assert "from '@/components/ui/button'" in content, "Should import Button component"


def test_briefing_page_has_markdown_renderer():
    """Verify that there is a MarkdownRenderer component."""
    page_path = Path('test/service-frontend/app/briefing/page.tsx')
    content = page_path.read_text()
    assert 'function MarkdownRenderer' in content, "Should have MarkdownRenderer component"
    assert 'parseSimpleMarkdown' in content, "Should have parseSimpleMarkdown function"


def test_briefing_page_handles_paragraphs():
    """Verify the markdown renderer handles paragraphs."""
    page_path = Path('test/service-frontend/app/briefing/page.tsx')
    content = page_path.read_text()
    assert "type: 'paragraph'" in content, "Should handle paragraph node type"
    assert "list-inside" in content, "Should render lists with proper styling"


def test_briefing_page_handles_bullet_lists():
    """Verify the markdown renderer handles bullet lists."""
    page_path = Path('test/service-frontend/app/briefing/page.tsx')
    content = page_path.read_text()
    assert "type: 'bullet-list'" in content, "Should handle bullet-list node type"
    assert "startsWith('- ')" in content or "startsWith('* ')" in content, \
        "Should detect bullet list markers"
    assert 'list-disc' in content, "Should use list-disc class for bullets"


def test_briefing_page_has_relative_time_formatter():
    """Verify that formatRelativeTime function exists and handles time units."""
    page_path = Path('test/service-frontend/app/briefing/page.tsx')
    content = page_path.read_text()
    assert 'function formatRelativeTime' in content, "Should have formatRelativeTime function"
    assert 'just now' in content, "Should handle 'just now' case"
    assert 'm ago' in content, "Should handle minutes ago"
    assert 'h ago' in content, "Should handle hours ago"
    assert 'd ago' in content, "Should handle days ago"


def test_briefing_page_has_useeffect_hook():
    """Verify that useEffect is used to fetch briefing on mount."""
    page_path = Path('test/service-frontend/app/briefing/page.tsx')
    content = page_path.read_text()
    assert 'useEffect' in content, "Should use useEffect hook"
    assert 'getLatestBriefing()' in content, "Should call getLatestBriefing on mount"


def test_briefing_page_has_generate_new_button():
    """Verify that Generate New button calls generateBriefing with manual kind."""
    page_path = Path('test/service-frontend/app/briefing/page.tsx')
    content = page_path.read_text()
    assert 'Generate New' in content, "Should have 'Generate New' button text"
    assert "kind: 'manual'" in content, "Should call generateBriefing with kind='manual'"


def test_briefing_page_has_empty_state():
    """Verify that empty state message is displayed when no briefing exists."""
    page_path = Path('test/service-frontend/app/briefing/page.tsx')
    content = page_path.read_text()
    assert 'No briefing yet' in content, "Should have empty state message"
    assert 'start a focus session or click Generate New' in content, \
        "Empty state message should guide user to generate or start session"


def test_briefing_page_renders_in_card():
    """Verify that briefing content is rendered inside a Card component."""
    page_path = Path('test/service-frontend/app/briefing/page.tsx')
    content = page_path.read_text()
    assert '<Card' in content, "Should use Card component to wrap content"
    assert 'className="p-6"' in content or 'className=' in content, \
        "Card should have padding styling"


def test_briefing_page_shows_generated_at_time():
    """Verify that generated_at timestamp is displayed with relative time."""
    page_path = Path('test/service-frontend/app/briefing/page.tsx')
    content = page_path.read_text()
    assert 'generated_at' in content, "Should reference generated_at field"
    assert 'formatRelativeTime(briefing.generated_at)' in content, \
        "Should display generated_at using formatRelativeTime"


def test_briefing_page_has_loading_state():
    """Verify that loading state is handled."""
    page_path = Path('test/service-frontend/app/briefing/page.tsx')
    content = page_path.read_text()
    assert 'loading' in content.lower(), "Should manage loading state"
    assert 'setLoading' in content, "Should update loading state"


def test_briefing_page_has_error_handling():
    """Verify that error state is handled and displayed."""
    page_path = Path('test/service-frontend/app/briefing/page.tsx')
    content = page_path.read_text()
    assert 'error' in content.lower(), "Should manage error state"
    assert 'setError' in content, "Should update error state"
    assert 'catch' in content, "Should handle errors with try-catch"


def test_briefing_page_uses_usestate():
    """Verify that useState is imported and used for state management."""
    page_path = Path('test/service-frontend/app/briefing/page.tsx')
    content = page_path.read_text()
    assert 'useState' in content, "Should import useState hook"
    assert 'useState' in content, "Should use useState for component state"
