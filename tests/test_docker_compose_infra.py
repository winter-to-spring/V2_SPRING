import pytest
import yaml
from pathlib import Path


def test_docker_compose_yml_exists():
    """Test that docker-compose.yml file exists."""
    compose_file = Path("test/infra/docker-compose.yml")
    assert compose_file.exists(), f"File {compose_file} does not exist"


def test_docker_compose_valid_yaml():
    """Test that docker-compose.yml is valid YAML."""
    compose_file = Path("test/infra/docker-compose.yml")
    with open(compose_file, "r") as f:
        content = yaml.safe_load(f)
    assert content is not None, "docker-compose.yml is not valid YAML"
    assert isinstance(content, dict), "docker-compose.yml root should be a dictionary"


def test_docker_compose_version():
    """Test that docker-compose version is set."""
    compose_file = Path("test/infra/docker-compose.yml")
    with open(compose_file, "r") as f:
        content = yaml.safe_load(f)
    assert "version" in content, "docker-compose.yml missing 'version'"
    assert content["version"] == "3.8", "docker-compose version should be 3.8"


def test_docker_compose_has_required_services():
    """Test that all required services are defined."""
    compose_file = Path("test/infra/docker-compose.yml")
    with open(compose_file, "r") as f:
        content = yaml.safe_load(f)
    
    services = content.get("services", {})
    required_services = ["postgres", "redis", "backend", "frontend", "nginx"]
    
    for service in required_services:
        assert service in services, f"Service '{service}' not found in docker-compose.yml"


def test_postgres_service_config():
    """Test postgres service configuration."""
    compose_file = Path("test/infra/docker-compose.yml")
    with open(compose_file, "r") as f:
        content = yaml.safe_load(f)
    
    postgres = content["services"]["postgres"]
    assert postgres["image"] == "pgvector/pgvector:pg16", "postgres image should be pgvector/pgvector:pg16"
    assert "environment" in postgres, "postgres missing environment"
    assert "POSTGRES_USER" in postgres["environment"], "postgres missing POSTGRES_USER"
    assert "POSTGRES_PASSWORD" in postgres["environment"], "postgres missing POSTGRES_PASSWORD"
    assert "POSTGRES_DB" in postgres["environment"], "postgres missing POSTGRES_DB"
    assert "volumes" in postgres, "postgres missing volumes"
    assert "healthcheck" in postgres, "postgres missing healthcheck"
    assert "networks" in postgres, "postgres missing networks"


def test_redis_service_config():
    """Test redis service configuration."""
    compose_file = Path("test/infra/docker-compose.yml")
    with open(compose_file, "r") as f:
        content = yaml.safe_load(f)
    
    redis = content["services"]["redis"]
    assert redis["image"] == "redis:7-alpine", "redis image should be redis:7-alpine"
    assert "healthcheck" in redis, "redis missing healthcheck"
    assert redis["healthcheck"]["test"][0] == "CMD", "redis healthcheck should use CMD"
    assert "networks" in redis, "redis missing networks"


def test_backend_service_config():
    """Test backend service configuration."""
    compose_file = Path("test/infra/docker-compose.yml")
    with open(compose_file, "r") as f:
        content = yaml.safe_load(f)
    
    backend = content["services"]["backend"]
    assert "build" in backend, "backend missing build"
    assert "../service-backend" in backend["build"]["context"], "backend should build from ../service-backend"
    assert "depends_on" in backend, "backend missing depends_on"
    assert "postgres" in backend["depends_on"], "backend should depend on postgres"
    assert "redis" in backend["depends_on"], "backend should depend on redis"
    assert "environment" in backend, "backend missing environment"
    assert backend["ports"] == ["8000:8000"], "backend should expose port 8000"
    assert "networks" in backend, "backend missing networks"
    
    env = backend["environment"]
    required_env_vars = [
        "DATABASE_URL", "REDIS_URL", "SLACK_CLIENT_ID", "SLACK_CLIENT_SECRET",
        "SLACK_SIGNING_SECRET", "OPENAI_API_KEY", "JWT_SECRET", "FRONTEND_URL", "BACKEND_URL"
    ]
    for var in required_env_vars:
        assert var in env, f"backend environment missing {var}"


def test_frontend_service_config():
    """Test frontend service configuration."""
    compose_file = Path("test/infra/docker-compose.yml")
    with open(compose_file, "r") as f:
        content = yaml.safe_load(f)
    
    frontend = content["services"]["frontend"]
    assert "build" in frontend, "frontend missing build"
    assert "../service-frontend" in frontend["build"]["context"], "frontend should build from ../service-frontend"
    assert "depends_on" in frontend, "frontend missing depends_on"
    assert "backend" in frontend["depends_on"], "frontend should depend on backend"
    assert "environment" in frontend, "frontend missing environment"
    assert "NEXT_PUBLIC_API_URL" in frontend["environment"], "frontend missing NEXT_PUBLIC_API_URL"
    assert frontend["ports"] == ["3000:3000"], "frontend should expose port 3000"
    assert "networks" in frontend, "frontend missing networks"


def test_nginx_service_config():
    """Test nginx service configuration."""
    compose_file = Path("test/infra/docker-compose.yml")
    with open(compose_file, "r") as f:
        content = yaml.safe_load(f)
    
    nginx = content["services"]["nginx"]
    assert nginx["image"] == "nginx:alpine", "nginx image should be nginx:alpine"
    assert "depends_on" in nginx, "nginx missing depends_on"
    assert nginx["ports"] == ["80:80"], "nginx should expose port 80"
    assert "volumes" in nginx, "nginx missing volumes"
    assert any("nginx.conf" in str(v) for v in nginx["volumes"]), "nginx should mount nginx.conf"
    assert "networks" in nginx, "nginx missing networks"


def test_docker_compose_has_network():
    """Test that docker-compose defines app_network."""
    compose_file = Path("test/infra/docker-compose.yml")
    with open(compose_file, "r") as f:
        content = yaml.safe_load(f)
    
    assert "networks" in content, "docker-compose.yml missing networks section"
    assert "app_network" in content["networks"], "app_network not defined"


def test_docker_compose_has_volumes():
    """Test that docker-compose defines postgres_data volume."""
    compose_file = Path("test/infra/docker-compose.yml")
    with open(compose_file, "r") as f:
        content = yaml.safe_load(f)
    
    assert "volumes" in content, "docker-compose.yml missing volumes section"
    assert "postgres_data" in content["volumes"], "postgres_data volume not defined"


def test_nginx_conf_exists():
    """Test that nginx.conf file exists."""
    nginx_conf = Path("test/infra/nginx.conf")
    assert nginx_conf.exists(), f"File {nginx_conf} does not exist"


def test_nginx_conf_has_reverse_proxy_config():
    """Test that nginx.conf contains reverse proxy configuration."""
    nginx_conf = Path("test/infra/nginx.conf")
    with open(nginx_conf, "r") as f:
        content = f.read()
    
    assert "upstream backend" in content or "server backend" in content, "nginx.conf missing backend upstream/server"
    assert "upstream frontend" in content or "server frontend" in content, "nginx.conf missing frontend upstream/server"
    assert "/api" in content, "nginx.conf missing /api route"
    assert "listen 80" in content, "nginx.conf should listen on port 80"


def test_env_example_exists():
    """Test that .env.example file exists."""
    env_file = Path("test/infra/.env.example")
    assert env_file.exists(), f"File {env_file} does not exist"


def test_env_example_has_required_variables():
    """Test that .env.example contains all required environment variables."""
    env_file = Path("test/infra/.env.example")
    with open(env_file, "r") as f:
        content = f.read()
    
    required_vars = [
        "DATABASE_URL", "REDIS_URL", "SLACK_CLIENT_ID", "SLACK_CLIENT_SECRET",
        "SLACK_SIGNING_SECRET", "OPENAI_API_KEY", "JWT_SECRET", "FRONTEND_URL", "BACKEND_URL"
    ]
    
    for var in required_vars:
        assert var in content, f".env.example missing {var}"
