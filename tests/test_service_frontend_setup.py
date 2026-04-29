import json
import re
from pathlib import Path


def test_package_json_exists_with_dependencies():
    """Verify package.json exists with required dependencies."""
    pkg_file = Path("test/service-frontend/package.json")
    assert pkg_file.exists(), "package.json not found"
    
    with open(pkg_file) as f:
        pkg = json.load(f)
    
    assert pkg["name"] == "service-frontend"
    assert "next" in pkg["dependencies"]
    assert "^16" in pkg["dependencies"]["next"]
    assert "react" in pkg["dependencies"]
    assert "^19" in pkg["dependencies"]["react"]
    assert "react-dom" in pkg["dependencies"]
    assert "^19" in pkg["dependencies"]["react-dom"]
    assert "typescript" in pkg["dependencies"]
    assert "tailwindcss" in pkg["dependencies"]
    assert "^4" in pkg["dependencies"]["tailwindcss"]
    
    radix_deps = [k for k in pkg["dependencies"] if k.startswith("@radix-ui/react-")]
    assert len(radix_deps) > 0, "No @radix-ui/react-* primitives found"
    
    assert "class-variance-authority" in pkg["dependencies"]
    assert "clsx" in pkg["dependencies"]
    assert "tailwind-merge" in pkg["dependencies"]
    assert "lucide-react" in pkg["dependencies"]


def test_tsconfig_json_exists():
    """Verify tsconfig.json exists."""
    tsconfig_file = Path("test/service-frontend/tsconfig.json")
    assert tsconfig_file.exists(), "tsconfig.json not found"
    
    with open(tsconfig_file) as f:
        tsconfig = json.load(f)
    
    assert "compilerOptions" in tsconfig


def test_next_config_mjs_exists():
    """Verify next.config.mjs exists."""
    next_config = Path("test/service-frontend/next.config.mjs")
    assert next_config.exists(), "next.config.mjs not found"
    content = next_config.read_text()
    assert "export default" in content


def test_postcss_config_mjs_exists():
    """Verify postcss.config.mjs exists."""
    postcss_config = Path("test/service-frontend/postcss.config.mjs")
    assert postcss_config.exists(), "postcss.config.mjs not found"
    content = postcss_config.read_text()
    assert "tailwindcss" in content.lower()
    assert "autoprefixer" in content.lower()


def test_tailwind_config_ts_exists_with_triage_colors():
    """Verify tailwind.config.ts exists with Triage color tokens."""
    tailwind_config = Path("test/service-frontend/tailwind.config.ts")
    assert tailwind_config.exists(), "tailwind.config.ts not found"
    content = tailwind_config.read_text()
    
    assert "critical" in content.lower() or "#ef4444" in content
    assert "high" in content.lower() or "#eab308" in content
    assert "medium" in content.lower() or "#3b82f6" in content
    assert "low" in content.lower() or "#6b7280" in content
    
    assert "dark" in content
    assert "class" in content


def test_globals_css_exists_with_tailwind_directives():
    """Verify globals.css exists with Tailwind directives."""
    globals_css = Path("test/service-frontend/app/globals.css")
    assert globals_css.exists(), "globals.css not found"
    content = globals_css.read_text()
    
    assert "@tailwind" in content or "@layer" in content
    assert "--background" in content or "--foreground" in content


def test_layout_tsx_exists_with_dark_class():
    """Verify layout.tsx exists, sets dark class, imports globals.css."""
    layout = Path("test/service-frontend/app/layout.tsx")
    assert layout.exists(), "layout.tsx not found"
    content = layout.read_text()
    
    assert "dark" in content
    assert "globals.css" in content
    assert "children" in content
    assert "min-h-screen" in content or "bg-background" in content
    assert "html" in content or "lang" in content


def test_page_tsx_exists_with_redirect():
    """Verify page.tsx exists with redirect to /dashboard."""
    page = Path("test/service-frontend/app/page.tsx")
    assert page.exists(), "page.tsx not found"
    content = page.read_text()
    
    assert "redirect" in content
    assert "dashboard" in content
    assert "next/navigation" in content


def test_readme_md_exists_and_short():
    """Verify README.md exists and is <= 20 lines."""
    readme = Path("test/service-frontend/README.md")
    assert readme.exists(), "README.md not found"
    content = readme.read_text()
    lines = content.split("\n")
    assert len(lines) <= 20, f"README.md has {len(lines)} lines, max 20 allowed"
