import json
import pytest
from pathlib import Path


def test_package_json_exists():
    """Test that package.json exists in the correct location."""
    package_json_path = Path("test/service-frontend/package.json")
    assert package_json_path.exists(), f"Expected {package_json_path} to exist"


def test_package_json_has_required_fields():
    """Test that package.json contains all required fields."""
    package_json_path = Path("test/service-frontend/package.json")
    with open(package_json_path, "r") as f:
        data = json.load(f)
    
    assert "name" in data
    assert data["name"] == "service-frontend"
    assert "version" in data
    assert "scripts" in data
    assert "dependencies" in data
    assert "devDependencies" in data


def test_package_json_scripts():
    """Test that all required scripts are present."""
    package_json_path = Path("test/service-frontend/package.json")
    with open(package_json_path, "r") as f:
        data = json.load(f)
    
    required_scripts = ["dev", "build", "start", "lint", "typecheck"]
    scripts = data.get("scripts", {})
    
    for script in required_scripts:
        assert script in scripts, f"Missing script: {script}"


def test_next_and_react_versions():
    """Test that Next.js and React versions are correct."""
    package_json_path = Path("test/service-frontend/package.json")
    with open(package_json_path, "r") as f:
        data = json.load(f)
    
    deps = data.get("dependencies", {})
    assert "next" in deps
    assert deps["next"].startswith("^16")
    assert "react" in deps
    assert deps["react"].startswith("^19")
    assert "react-dom" in deps
    assert "typescript" in deps


def test_tailwind_and_shadcn_deps():
    """Test that Tailwind and shadcn/ui dependencies are present."""
    package_json_path = Path("test/service-frontend/package.json")
    with open(package_json_path, "r") as f:
        data = json.load(f)
    
    deps = data.get("dependencies", {})
    
    # Tailwind
    assert "tailwindcss" in deps
    assert deps["tailwindcss"].startswith("^4")
    
    # shadcn/ui core deps
    assert "class-variance-authority" in deps
    assert "clsx" in deps
    assert "tailwind-merge" in deps
    assert "lucide-react" in deps
    
    # Radix UI
    assert "@radix-ui/react-slot" in deps
    assert "@radix-ui/react-dialog" in deps
    assert "@radix-ui/react-dropdown-menu" in deps
    assert "@radix-ui/react-tabs" in deps
    assert "@radix-ui/react-toast" in deps


def test_utility_and_form_deps():
    """Test that utility and form management dependencies are present."""
    package_json_path = Path("test/service-frontend/package.json")
    with open(package_json_path, "r") as f:
        data = json.load(f)
    
    deps = data.get("dependencies", {})
    
    # Notifications
    assert "sonner" in deps
    
    # Data fetching
    assert "swr" in deps
    
    # Validation and forms
    assert "zod" in deps
    assert "react-hook-form" in deps


def test_tsconfig_exists():
    """Test that tsconfig.json exists."""
    tsconfig_path = Path("test/service-frontend/tsconfig.json")
    assert tsconfig_path.exists(), "tsconfig.json should exist"


def test_tsconfig_has_path_aliases():
    """Test that tsconfig.json has @/* path alias."""
    tsconfig_path = Path("test/service-frontend/tsconfig.json")
    with open(tsconfig_path, "r") as f:
        data = json.load(f)
    
    assert "compilerOptions" in data
    assert "paths" in data["compilerOptions"]
    assert "@/*" in data["compilerOptions"]["paths"]


def test_next_config_exists():
    """Test that next.config.ts exists."""
    next_config_path = Path("test/service-frontend/next.config.ts")
    assert next_config_path.exists(), "next.config.ts should exist"


def test_tailwind_config_exists():
    """Test that tailwind.config.ts exists."""
    tailwind_config_path = Path("test/service-frontend/tailwind.config.ts")
    assert tailwind_config_path.exists(), "tailwind.config.ts should exist"


def test_tailwind_config_dark_mode():
    """Test that tailwind.config.ts has dark mode set to class."""
    tailwind_config_path = Path("test/service-frontend/tailwind.config.ts")
    content = tailwind_config_path.read_text()
    
    assert "darkMode:" in content or "darkMode :" in content
    assert "'class'" in content or '"class"' in content


def test_postcss_config_exists():
    """Test that postcss.config.mjs exists."""
    postcss_config_path = Path("test/service-frontend/postcss.config.mjs")
    assert postcss_config_path.exists(), "postcss.config.mjs should exist"


def test_dockerfile_exists():
    """Test that Dockerfile exists in service-frontend directory."""
    dockerfile_path = Path("test/service-frontend/Dockerfile")
    assert dockerfile_path.exists(), "Dockerfile should exist"


def test_dockerfile_node_alpine():
    """Test that Dockerfile uses node:20-alpine."""
    dockerfile_path = Path("test/service-frontend/Dockerfile")
    content = dockerfile_path.read_text()
    
    assert "node:20-alpine" in content
    assert "npm ci" in content
    assert "npm run build" in content
    assert "npm start" in content


def test_dockerignore_exists():
    """Test that .dockerignore exists."""
    dockerignore_path = Path("test/service-frontend/.dockerignore")
    assert dockerignore_path.exists(), ".dockerignore should exist"


def test_env_local_example_exists():
    """Test that .env.local.example exists."""
    env_example_path = Path("test/service-frontend/.env.local.example")
    assert env_example_path.exists(), ".env.local.example should exist"


def test_env_local_example_content():
    """Test that .env.local.example has NEXT_PUBLIC_API_URL."""
    env_example_path = Path("test/service-frontend/.env.local.example")
    content = env_example_path.read_text()
    
    assert "NEXT_PUBLIC_API_URL" in content
    assert "http://localhost:8000" in content
