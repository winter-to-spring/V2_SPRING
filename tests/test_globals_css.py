import pytest


def test_globals_css_exists():
    """Verify globals.css file exists at expected path."""
    css_path = "test/service-frontend/src/app/globals.css"
    with open(css_path) as f:
        content = f.read()
    assert content, "globals.css should not be empty"


def test_globals_css_has_tailwind_import():
    """Verify Tailwind v4 import directive is present."""
    css_path = "test/service-frontend/src/app/globals.css"
    with open(css_path) as f:
        content = f.read()
    assert '@import "tailwindcss"' in content


def test_globals_css_has_root_variables():
    """Verify CSS custom properties are defined in :root."""
    css_path = "test/service-frontend/src/app/globals.css"
    with open(css_path) as f:
        content = f.read()
    required_vars = [
        "--background",
        "--foreground",
        "--card",
        "--primary",
        "--muted",
        "--border",
        "--ring",
    ]
    for var in required_vars:
        assert var in content, f"CSS variable {var} should be defined in :root"


def test_globals_css_has_dark_theme():
    """Verify dark theme CSS variables are defined in html.dark."""
    css_path = "test/service-frontend/src/app/globals.css"
    with open(css_path) as f:
        content = f.read()
    assert "html.dark {" in content, "Dark theme block should exist"
    dark_section = content[content.find("html.dark {") : content.find("html.dark {") + 500]
    assert "--background: 0 0% 3.6%;" in dark_section
    assert "--foreground: 0 0% 98%;" in dark_section


def test_globals_css_has_triage_tokens():
    """Verify triage priority color tokens are defined."""
    css_path = "test/service-frontend/src/app/globals.css"
    with open(css_path) as f:
        content = f.read()
    triage_tokens = [
        "--triage-critical",
        "--triage-high",
        "--triage-medium",
        "--triage-low",
    ]
    for token in triage_tokens:
        assert token in content, f"Triage token {token} should be defined"


def test_globals_css_has_layer_directives():
    """Verify Tailwind @layer directives are present."""
    css_path = "test/service-frontend/src/app/globals.css"
    with open(css_path) as f:
        content = f.read()
    assert "@layer base" in content, "@layer base directive should be present"


def test_globals_css_has_body_styling():
    """Verify body element receives background and foreground styling."""
    css_path = "test/service-frontend/src/app/globals.css"
    with open(css_path) as f:
        content = f.read()
    assert "body {" in content
    body_section = content[content.find("body {") : content.find("body {") + 300]
    assert "--background" in body_section
    assert "--foreground" in body_section
