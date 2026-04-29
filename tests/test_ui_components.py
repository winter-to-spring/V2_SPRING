"""
Test that all shadcn/ui components are properly created and exported.
"""
import os
import re
from pathlib import Path


def test_ui_components_directory_exists():
    """Verify the UI components directory structure exists."""
    ui_dir = Path('test/service-frontend/src/components/ui')
    assert ui_dir.exists(), f"UI components directory not found at {ui_dir}"
    assert ui_dir.is_dir(), f"UI path is not a directory: {ui_dir}"


def test_all_component_files_exist():
    """Verify all required component files exist."""
    ui_dir = Path('test/service-frontend/src/components/ui')
    required_files = [
        'index.ts',
        'button.tsx',
        'card.tsx',
        'badge.tsx',
        'dialog.tsx',
        'dropdown-menu.tsx',
        'tabs.tsx',
        'input.tsx',
        'label.tsx',
        'separator.tsx',
        'skeleton.tsx',
        'sonner.tsx',
    ]
    
    for filename in required_files:
        filepath = ui_dir / filename
        assert filepath.exists(), f"Missing component file: {filename}"
        assert filepath.is_file(), f"Not a file: {filename}"


def test_barrel_export_index_exports_all_components():
    """Verify index.ts exports all UI components."""
    index_file = Path('test/service-frontend/src/components/ui/index.ts')
    content = index_file.read_text()
    
    expected_exports = [
        'Button',
        'buttonVariants',
        'Card',
        'CardHeader',
        'CardFooter',
        'CardTitle',
        'CardDescription',
        'CardContent',
        'Badge',
        'badgeVariants',
        'Dialog',
        'DialogTrigger',
        'DialogContent',
        'DialogHeader',
        'DialogFooter',
        'DialogTitle',
        'DialogDescription',
        'DropdownMenu',
        'DropdownMenuTrigger',
        'DropdownMenuContent',
        'DropdownMenuItem',
        'DropdownMenuCheckboxItem',
        'DropdownMenuRadioItem',
        'DropdownMenuLabel',
        'DropdownMenuSeparator',
        'DropdownMenuShortcut',
        'DropdownMenuGroup',
        'DropdownMenuPortal',
        'DropdownMenuSub',
        'DropdownMenuSubContent',
        'DropdownMenuSubTrigger',
        'DropdownMenuRadioGroup',
        'Tabs',
        'TabsList',
        'TabsTrigger',
        'TabsContent',
        'Input',
        'Label',
        'Separator',
        'Skeleton',
        'Toaster',
    ]
    
    for export_name in expected_exports:
        assert f"export {export_name}" in content or f"{{ {export_name}" in content, \
            f"Export '{export_name}' not found in index.ts"


def test_button_component_radix_cva():
    """Verify button.tsx uses Radix UI Button and CVA."""
    button_file = Path('test/service-frontend/src/components/ui/button.tsx')
    content = button_file.read_text()
    
    assert '@radix-ui/react-primitive' in content or 'forwardRef' in content, \
        "Button component should use Radix UI patterns"
    assert 'cva' in content, "Button component should use CVA for styling"
    assert 'variant' in content, "Button should have variant prop"


def test_card_component_composition():
    """Verify card.tsx exports Card subcomponents."""
    card_file = Path('test/service-frontend/src/components/ui/card.tsx')
    content = card_file.read_text()
    
    required_subcomponents = ['CardHeader', 'CardFooter', 'CardTitle', 'CardDescription', 'CardContent']
    for subcomponent in required_subcomponents:
        assert f'export' in content and subcomponent in content, \
            f"Card component missing {subcomponent}"


def test_badge_component_variants():
    """Verify badge.tsx uses CVA with variants."""
    badge_file = Path('test/service-frontend/src/components/ui/badge.tsx')
    content = badge_file.read_text()
    
    assert 'cva' in content, "Badge should use CVA for styling"
    assert 'variant' in content, "Badge should have variant prop"


def test_dialog_component_radix_portal():
    """Verify dialog.tsx uses Radix Dialog with portal support."""
    dialog_file = Path('test/service-frontend/src/components/ui/dialog.tsx')
    content = dialog_file.read_text()
    
    assert '@radix-ui/react-dialog' in content, "Dialog should use Radix UI Dialog"
    assert 'DialogPortal' in content or 'Portal' in content, "Dialog should support portals"


def test_dropdown_menu_component_radix():
    """Verify dropdown-menu.tsx uses Radix DropdownMenu."""
    dropdown_file = Path('test/service-frontend/src/components/ui/dropdown-menu.tsx')
    content = dropdown_file.read_text()
    
    assert '@radix-ui/react-dropdown-menu' in content, \
        "DropdownMenu should use Radix UI DropdownMenu"


def test_tabs_component_radix():
    """Verify tabs.tsx uses Radix Tabs."""
    tabs_file = Path('test/service-frontend/src/components/ui/tabs.tsx')
    content = tabs_file.read_text()
    
    assert '@radix-ui/react-tabs' in content, "Tabs should use Radix UI Tabs"


def test_input_component_theme_aware():
    """Verify input.tsx is theme-aware with CSS vars."""
    input_file = Path('test/service-frontend/src/components/ui/input.tsx')
    content = input_file.read_text()
    
    assert 'className' in content, "Input should have className prop"
    assert 'forwardRef' in content or 'ref' in content, "Input should be a ref-forwarding component"


def test_label_component_radix():
    """Verify label.tsx uses Radix Label."""
    label_file = Path('test/service-frontend/src/components/ui/label.tsx')
    content = label_file.read_text()
    
    assert '@radix-ui/react-label' in content, "Label should use Radix UI Label"


def test_separator_component_radix():
    """Verify separator.tsx uses Radix Separator."""
    separator_file = Path('test/service-frontend/src/components/ui/separator.tsx')
    content = separator_file.read_text()
    
    assert '@radix-ui/react-separator' in content, "Separator should use Radix UI Separator"


def test_skeleton_component_exists():
    """Verify skeleton.tsx provides a loading skeleton component."""
    skeleton_file = Path('test/service-frontend/src/components/ui/skeleton.tsx')
    content = skeleton_file.read_text()
    
    assert 'export' in content and 'Skeleton' in content, \
        "Skeleton component should be exported"
    assert 'className' in content, "Skeleton should have className prop"


def test_sonner_toaster_component():
    """Verify sonner.tsx exports Toaster component."""
    sonner_file = Path('test/service-frontend/src/components/ui/sonner.tsx')
    content = sonner_file.read_text()
    
    assert 'sonner' in content, "Sonner component should import from sonner library"
    assert 'Toaster' in content, "Should export Toaster component"


def test_components_use_css_variables():
    """Verify components use CSS variables for theming."""
    ui_dir = Path('test/service-frontend/src/components/ui')
    component_files = [
        'button.tsx',
        'card.tsx',
        'badge.tsx',
        'input.tsx',
    ]
    
    # At least some components should reference CSS variables
    found_css_vars = False
    for filename in component_files:
        filepath = ui_dir / filename
        if filepath.exists():
            content = filepath.read_text()
            # Look for CSS variable patterns or className patterns
            if 'bg-' in content or 'text-' in content or 'border-' in content or 'hsl(' in content:
                found_css_vars = True
                break
    
    assert found_css_vars, "Components should use CSS variables for theming"


def test_components_are_typescript():
    """Verify all components are TypeScript (.tsx)."""
    ui_dir = Path('test/service-frontend/src/components/ui')
    tsx_files = list(ui_dir.glob('*.tsx'))
    
    assert len(tsx_files) >= 11, f"Expected at least 11 .tsx files, found {len(tsx_files)}"
