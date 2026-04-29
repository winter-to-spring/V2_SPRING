import ast
import inspect
import sys
from pathlib import Path


def test_db_init_exports():
    """Test that __init__.py exports Base and get_db."""
    init_file = Path("test/service-backend/app/db/__init__.py")
    assert init_file.exists(), f"{init_file} does not exist"
    
    content = init_file.read_text()
    tree = ast.parse(content)
    
    # Check for imports
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            imports.append((node.module, [alias.name for alias in node.names]))
    
    assert any(".base" in str(imp) for imp in imports), "Missing import from .base"
    assert any(".session" in str(imp) for imp in imports), "Missing import from .session"
    
    # Check for __all__
    has_all = any(
        isinstance(node, ast.Assign) and 
        isinstance(node.targets[0], ast.Name) and 
        node.targets[0].id == "__all__"
        for node in ast.walk(tree)
    )
    assert has_all, "Missing __all__ definition"


def test_db_base_exists():
    """Test that base.py exists and contains Base."""
    base_file = Path("test/service-backend/app/db/base.py")
    assert base_file.exists(), f"{base_file} does not exist"
    
    content = base_file.read_text()
    assert "Base" in content, "Base not defined in base.py"
    assert "DeclarativeBase" in content, "DeclarativeBase not imported in base.py"


def test_db_session_exists():
    """Test that session.py exists and contains async engine and get_db."""
    session_file = Path("test/service-backend/app/db/session.py")
    assert session_file.exists(), f"{session_file} does not exist"
    
    content = session_file.read_text()
    tree = ast.parse(content)
    
    # Check for create_async_engine import
    assert "create_async_engine" in content, "create_async_engine not imported"
    
    # Check for async_sessionmaker import
    assert "async_sessionmaker" in content, "async_sessionmaker not imported"
    
    # Check for AsyncSession import
    assert "AsyncSession" in content, "AsyncSession not imported"
    
    # Check for engine variable assignment
    assert "engine" in content, "engine variable not defined"
    assert "DATABASE_URL" in content, "DATABASE_URL reference not found"
    
    # Check for async_session_maker or sessionmaker variable
    assert "async_sessionmaker" in content or "sessionmaker" in content, "async_sessionmaker setup not found"
    
    # Check for get_db function
    functions = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef)]
    assert "get_db" in functions, "get_db function not found"
    
    # Check that get_db is async
    get_db_node = None
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "get_db":
            get_db_node = node
            break
    
    assert get_db_node is not None, "get_db must be an async function"
    
    # Check for yield in get_db (FastAPI dependency pattern)
    has_yield = any(isinstance(n, ast.Yield) for n in ast.walk(get_db_node))
    assert has_yield, "get_db should use yield for FastAPI dependency"


def test_db_structure():
    """Test that all three files exist in correct directory structure."""
    db_dir = Path("test/service-backend/app/db")
    assert db_dir.is_dir(), f"{db_dir} is not a directory"
    
    required_files = [
        "test/service-backend/app/db/__init__.py",
        "test/service-backend/app/db/base.py",
        "test/service-backend/app/db/session.py",
    ]
    
    for file_path in required_files:
        assert Path(file_path).exists(), f"{file_path} does not exist"


def test_session_imports_settings():
    """Test that session.py imports settings for DATABASE_URL."""
    session_file = Path("test/service-backend/app/db/session.py")
    content = session_file.read_text()
    
    tree = ast.parse(content)
    
    # Check for import of settings
    has_settings_import = False
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module and "settings" in node.module:
                has_settings_import = True
                break
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if "settings" in alias.name:
                    has_settings_import = True
                    break
    
    assert has_settings_import, "settings module not imported in session.py"
