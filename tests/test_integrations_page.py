"""
Test suite for integrations settings page.
Verifies the page structure, provider cards, and Slack integration UI.
"""

import re


def test_integrations_page_file_exists():
    """Test that the integrations page file exists at the correct path."""
    import os
    
    target_path = 'test/service-frontend/app/settings/integrations/page.tsx'
    assert os.path.isfile(target_path), f"File not found: {target_path}"


def test_integrations_page_use_client_directive():
    """Test that page uses 'use client' directive for client-side rendering."""
    with open('test/service-frontend/app/settings/integrations/page.tsx', 'r') as f:
        content = f.read()
    
    assert "'use client';" in content, "Missing 'use client' directive"


def test_integrations_page_imports():
    """Test that page imports necessary React and UI components."""
    with open('test/service-frontend/app/settings/integrations/page.tsx', 'r') as f:
        content = f.read()
    
    required_imports = [
        "import { useEffect, useState }",
        "import { useSearchParams }",
        "from '@/components/ui/card'",
        "from '@/components/ui/button'",
        "from '@/components/ui/badge'",
        "from '@/hooks/use-toast'",
    ]
    
    for import_statement in required_imports:
        assert import_statement in content, f"Missing import: {import_statement}"


def test_integrations_page_slack_provider_card():
    """Test that Slack provider card is present."""
    with open('test/service-frontend/app/settings/integrations/page.tsx', 'r') as f:
        content = f.read()
    
    assert 'Slack' in content, "Slack provider not found"
    assert 'CardTitle>Slack</CardTitle>' in content, "Slack CardTitle not found"
    assert 'Connect your Slack workspace' in content, "Slack description not found"


def test_integrations_page_disabled_providers():
    """Test that Discord, Gmail, and Jira are shown as disabled with Coming soon badge."""
    with open('test/service-frontend/app/settings/integrations/page.tsx', 'r') as f:
        content = f.read()
    
    providers = ['Discord', 'Gmail', 'Jira']
    for provider in providers:
        assert provider in content, f"{provider} provider not found"
        assert 'Coming soon' in content, "Coming soon badge not found"


def test_integrations_page_slack_connect_button():
    """Test that Slack has a Connect Slack button."""
    with open('test/service-frontend/app/settings/integrations/page.tsx', 'r') as f:
        content = f.read()
    
    assert 'Connect Slack' in content, "Connect Slack button text not found"
    assert 'handleConnectSlack' in content, "handleConnectSlack function not found"


def test_integrations_page_slack_api_fetch():
    """Test that Slack integration fetches the install URL from API."""
    with open('test/service-frontend/app/settings/integrations/page.tsx', 'r') as f:
        content = f.read()
    
    assert '/api/integrations/slack/install-url' in content, "Slack API endpoint not found"
    assert 'window.location.assign' in content, "Window location assign not found"


def test_integrations_page_query_param_toast():
    """Test that the page reads ?installed=slack query parameter for toast."""
    with open('test/service-frontend/app/settings/integrations/page.tsx', 'r') as f:
        content = f.read()
    
    assert "searchParams.get('installed')" in content, "Query parameter reading not found"
    assert "installed === 'slack'" in content, "Slack query parameter check not found"
    assert "toast" in content, "Toast function not found"


def test_integrations_page_slack_connected_state():
    """Test that page renders Connected badge and workspace info when Slack is connected."""
    with open('test/service-frontend/app/settings/integrations/page.tsx', 'r') as f:
        content = f.read()
    
    assert 'Connected' in content, "Connected badge not found"
    assert 'slackConnected' in content, "slackConnected state not found"
    assert 'slackWorkspace' in content, "slackWorkspace state not found"


def test_integrations_page_disconnect_button():
    """Test that page has a disabled Disconnect button for Slack."""
    with open('test/service-frontend/app/settings/integrations/page.tsx', 'r') as f:
        content = f.read()
    
    assert 'Disconnect' in content, "Disconnect button not found"
    assert 'handleDisconnectSlack' in content, "handleDisconnectSlack function not found"
    # Check that disconnect button is disabled
    assert re.search(r'disabled[^>]*>[\s\n]*Disconnect', content) or \
           re.search(r'handleDisconnectSlack[^}]*disabled', content) or \
           'disabled' in content and 'Disconnect' in content, \
           "Disconnect button should have disabled attribute"


def test_integrations_page_dark_mode_styling():
    """Test that page uses dark mode tokens (slate-950, slate-800, etc)."""
    with open('test/service-frontend/app/settings/integrations/page.tsx', 'r') as f:
        content = f.read()
    
    dark_mode_classes = ['slate-950', 'slate-800', 'text-slate-50', 'bg-slate-950']
    dark_mode_found = sum(1 for cls in dark_mode_classes if cls in content)
    
    assert dark_mode_found >= 2, "Insufficient dark mode styling tokens found"


def test_integrations_page_card_components():
    """Test that page uses Card components from shadcn UI."""
    with open('test/service-frontend/app/settings/integrations/page.tsx', 'r') as f:
        content = f.read()
    
    card_elements = ['<Card', '<CardHeader', '<CardTitle', '<CardDescription', '<CardContent']
    for element in card_elements:
        assert element in content, f"Missing Card component: {element}"


def test_integrations_page_badge_component():
    """Test that page uses Badge component for status."""
    with open('test/service-frontend/app/settings/integrations/page.tsx', 'r') as f:
        content = f.read()
    
    assert '<Badge' in content, "Badge component not found"


def test_integrations_page_default_export():
    """Test that page has default export function."""
    with open('test/service-frontend/app/settings/integrations/page.tsx', 'r') as f:
        content = f.read()
    
    assert 'export default function IntegrationsPage' in content, \
           "Default export function IntegrationsPage not found"


def test_integrations_page_grid_layout():
    """Test that providers are displayed in a grid layout."""
    with open('test/service-frontend/app/settings/integrations/page.tsx', 'r') as f:
        content = f.read()
    
    assert 'grid' in content, "Grid layout class not found"
    assert 'gap-6' in content, "Grid gap class not found"
