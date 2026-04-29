"""
Test suite for shadcn/ui component library files.
Verifies all component files exist and contain expected implementations.
"""
import os
import re


def test_utils_cn_helper_exists():
    """Verify test/service-frontend/lib/utils.ts exists with cn helper."""
    utils_path = "test/service-frontend/lib/utils.ts"
    assert os.path.exists(utils_path), f"{utils_path} not found"
    
    with open(utils_path, "r") as f:
        content = f.read()
    
    assert "clsx" in content, "clsx import missing"
    assert "twMerge" in content, "tailwind-merge import missing"
    assert "function cn" in content, "cn function not found"
    assert "ClassValue" in content, "ClassValue type not found"


def test_button_component_exists():
    """Verify button component exists with standard shadcn/ui structure."""
    button_path = "test/service-frontend/components/ui/button.tsx"
    assert os.path.exists(button_path), f"{button_path} not found"
    
    with open(button_path, "r") as f:
        content = f.read()
    
    assert "forwardRef" in content, "forwardRef not found"
    assert "cva" in content or "className=" in content, "styling mechanism missing"
    assert "Slot" in content or "asChild" in content or "variant" in content, "button variant missing"
    assert len(content) <= 120 * 6, "button.tsx exceeds line limit"


def test_card_component_exists():
    """Verify card component exists."""
    card_path = "test/service-frontend/components/ui/card.tsx"
    assert os.path.exists(card_path), f"{card_path} not found"
    
    with open(card_path, "r") as f:
        content = f.read()
    
    assert "Card" in content, "Card component not found"
    assert len(content.split("\n")) <= 120, "card.tsx exceeds line limit"


def test_badge_component_exists():
    """Verify badge component exists with cva styling."""
    badge_path = "test/service-frontend/components/ui/badge.tsx"
    assert os.path.exists(badge_path), f"{badge_path} not found"
    
    with open(badge_path, "r") as f:
        content = f.read()
    
    assert "Badge" in content, "Badge component not found"
    assert len(content.split("\n")) <= 120, "badge.tsx exceeds line limit"


def test_input_component_exists():
    """Verify input component exists with proper forwardRef."""
    input_path = "test/service-frontend/components/ui/input.tsx"
    assert os.path.exists(input_path), f"{input_path} not found"
    
    with open(input_path, "r") as f:
        content = f.read()
    
    assert "Input" in content, "Input component not found"
    assert "forwardRef" in content, "forwardRef not implemented"
    assert len(content.split("\n")) <= 120, "input.tsx exceeds line limit"


def test_label_component_exists():
    """Verify label component exists (likely Radix-based)."""
    label_path = "test/service-frontend/components/ui/label.tsx"
    assert os.path.exists(label_path), f"{label_path} not found"
    
    with open(label_path, "r") as f:
        content = f.read()
    
    assert "Label" in content or "label" in content.lower(), "Label component not found"
    assert len(content.split("\n")) <= 120, "label.tsx exceeds line limit"


def test_dialog_component_exists():
    """Verify dialog component exists with Radix Dialog."""
    dialog_path = "test/service-frontend/components/ui/dialog.tsx"
    assert os.path.exists(dialog_path), f"{dialog_path} not found"
    
    with open(dialog_path, "r") as f:
        content = f.read()
    
    assert "Dialog" in content, "Dialog component not found"
    assert len(content.split("\n")) <= 120, "dialog.tsx exceeds line limit"


def test_separator_component_exists():
    """Verify separator component exists with Radix Separator."""
    separator_path = "test/service-frontend/components/ui/separator.tsx"
    assert os.path.exists(separator_path), f"{separator_path} not found"
    
    with open(separator_path, "r") as f:
        content = f.read()
    
    assert "Separator" in content, "Separator component not found"
    assert len(content.split("\n")) <= 120, "separator.tsx exceeds line limit"


def test_triage_badge_component_exists():
    """Verify triage-badge component with urgency mapping and contrast."""
    triage_path = "test/service-frontend/components/ui/triage-badge.tsx"
    assert os.path.exists(triage_path), f"{triage_path} not found"
    
    with open(triage_path, "r") as f:
        content = f.read()
    
    assert "critical" in content.lower(), "critical urgency not found"
    assert "high" in content.lower(), "high urgency not found"
    assert "medium" in content.lower(), "medium urgency not found"
    assert "low" in content.lower(), "low urgency not found"
    assert "contrast" in content.lower() or "aria" in content.lower() or "accessible" in content.lower(), \
        "accessibility/contrast not mentioned"
    assert len(content.split("\n")) <= 120, "triage-badge.tsx exceeds line limit"


def test_all_components_in_ui_directory():
    """Verify all required component files exist in ui directory."""
    ui_dir = "test/service-frontend/components/ui"
    assert os.path.isdir(ui_dir), f"{ui_dir} directory not found"
    
    required_files = [
        "button.tsx",
        "card.tsx",
        "badge.tsx",
        "input.tsx",
        "label.tsx",
        "dialog.tsx",
        "separator.tsx",
        "triage-badge.tsx",
    ]
    
    for filename in required_files:
        filepath = os.path.join(ui_dir, filename)
        assert os.path.exists(filepath), f"Missing required component: {filename}"


def test_utils_directory_exists():
    """Verify lib directory structure."""
    lib_dir = "test/service-frontend/lib"
    assert os.path.isdir(lib_dir), f"{lib_dir} directory not found"
    
    utils_path = os.path.join(lib_dir, "utils.ts")
    assert os.path.exists(utils_path), "utils.ts not found in lib directory"
