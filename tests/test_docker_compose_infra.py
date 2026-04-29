import os
import yaml
import pytest


def test_docker_compose_file_exists():
    """Test that docker-compose.yml exists in test/infra directory."""
    compose_file = "test/infra/docker-compose.yml"
    assert os.path.exists(compose_file), f"File {compose_file} does not exist"


def test_docker_compose_yaml_valid():
    """Test that docker-compose.yml is valid YAML."""
    compose_file = "test/infra/docker-compose.yml"
    with open(compose_file, 'r') as f:
        content = yaml.safe_load(f)
    assert content is not None, "docker-compose.yml is not valid YAML"


def test_docker_compose_services():
    """Test that all required services are defined."""
    compose_file = "test/infra/docker-compose.yml"
    with open(compose_file, 'r') as f:
        content = yaml.safe_load(f)
    
    services = content.get('services', {})
    required_services = ['postgres', 'redis', 'backend', 'frontend', 'nginx']
    
    for service in required_services:
        assert service in services, f"Service '{service}' not found in docker-compose.yml"


def test_postgres_configuration():
    """Test that postgres service has correct image and healthcheck."""
    compose_file = "test/infra/docker-compose.yml"
    with open(compose_file, 'r') as f:
        content = yaml.safe_load(f)
    
    postgres = content['services']['postgres']
    assert postgres['image'] == 'pgvector/pgvector:pg16', "Postgres image is not pgvector:pg16"
    assert 'healthcheck' in postgres, "Postgres healthcheck is missing"
    assert 'pg_isready' in str(postgres['healthcheck']['test']), "Healthcheck should use pg_isready"


def test_redis_configuration():
    """Test that redis service has correct image and healthcheck."""
    compose_file = "test/infra/docker-compose.yml"
    with open(compose_file, 'r') as f:
        content = yaml.safe_load(f)
    
    redis = content['services']['redis']
    assert redis['image'] == 'redis:7-alpine', "Redis image is not redis:7-alpine"
    assert 'healthcheck' in redis, "Redis healthcheck is missing"
    assert 'redis-cli ping' in str(redis['healthcheck']['test']), "Healthcheck should use redis-cli ping"


def test_backend_configuration():
    """Test that backend service has correct build context and dependencies."""
    compose_file = "test/infra/docker-compose.yml"
    with open(compose_file, 'r') as f:
        content = yaml.safe_load(f)
    
    backend = content['services']['backend']
    assert backend['build']['context'] == '../service-backend', "Backend build context is incorrect"
    assert 'env_file' in backend, "Backend env_file is missing"
    assert '../service-backend/.env' in backend['env_file'], "Backend env_file path is incorrect"
    assert backend['ports'] == ['8000:8000'], "Backend port mapping is incorrect"
    assert 'depends_on' in backend, "Backend depends_on is missing"
    assert 'postgres' in backend['depends_on'], "Backend should depend on postgres"
    assert 'redis' in backend['depends_on'], "Backend should depend on redis"


def test_frontend_configuration():
    """Test that frontend service has correct build context and environment."""
    compose_file = "test/infra/docker-compose.yml"
    with open(compose_file, 'r') as f:
        content = yaml.safe_load(f)
    
    frontend = content['services']['frontend']
    assert frontend['build']['context'] == '../service-frontend', "Frontend build context is incorrect"
    assert frontend['ports'] == ['3000:3000'], "Frontend port mapping is incorrect"
    assert 'environment' in frontend, "Frontend environment is missing"
    assert frontend['environment']['NEXT_PUBLIC_API_BASE'] == 'http://localhost:8000', "Frontend NEXT_PUBLIC_API_BASE is incorrect"


def test_nginx_configuration():
    """Test that nginx service has correct image and mounts."""
    compose_file = "test/infra/docker-compose.yml"
    with open(compose_file, 'r') as f:
        content = yaml.safe_load(f)
    
    nginx = content['services']['nginx']
    assert nginx['image'] == 'nginx:alpine', "Nginx image is not nginx:alpine"
    assert nginx['ports'] == ['80:80'], "Nginx port mapping is incorrect"
    assert 'volumes' in nginx, "Nginx volumes are missing"
    assert './nginx.conf:/etc/nginx/nginx.conf:ro' in nginx['volumes'], "Nginx config mount is incorrect"


def test_named_volumes():
    """Test that named volumes pgdata and redisdata are defined."""
    compose_file = "test/infra/docker-compose.yml"
    with open(compose_file, 'r') as f:
        content = yaml.safe_load(f)
    
    volumes = content.get('volumes', {})
    assert 'pgdata' in volumes, "Named volume 'pgdata' is not defined"
    assert 'redisdata' in volumes, "Named volume 'redisdata' is not defined"


def test_volumes_mounted():
    """Test that postgres and redis services mount the named volumes."""
    compose_file = "test/infra/docker-compose.yml"
    with open(compose_file, 'r') as f:
        content = yaml.safe_load(f)
    
    postgres = content['services']['postgres']
    redis = content['services']['redis']
    
    assert 'pgdata:/var/lib/postgresql/data' in postgres['volumes'], "Postgres should mount pgdata volume"
    assert 'redisdata:/data' in redis['volumes'], "Redis should mount redisdata volume"


def test_network_defined():
    """Test that infra network is defined."""
    compose_file = "test/infra/docker-compose.yml"
    with open(compose_file, 'r') as f:
        content = yaml.safe_load(f)
    
    networks = content.get('networks', {})
    assert 'infra' in networks, "Network 'infra' is not defined"


def test_nginx_conf_file_exists():
    """Test that nginx.conf exists."""
    nginx_conf = "test/infra/nginx.conf"
    assert os.path.exists(nginx_conf), f"File {nginx_conf} does not exist"


def test_nginx_conf_upstream_blocks():
    """Test that nginx.conf has upstream blocks for backend and frontend."""
    nginx_conf = "test/infra/nginx.conf"
    with open(nginx_conf, 'r') as f:
        content = f.read()
    
    assert 'upstream' in content, "nginx.conf should define upstream blocks"
    assert 'backend' in content or 'localhost:8000' in content, "nginx.conf should reference backend"
    assert 'frontend' in content or 'localhost:3000' in content, "nginx.conf should reference frontend"


def test_nginx_conf_proxy_pass():
    """Test that nginx.conf has proxy_pass rules."""
    nginx_conf = "test/infra/nginx.conf"
    with open(nginx_conf, 'r') as f:
        content = f.read()
    
    assert 'proxy_pass' in content, "nginx.conf should have proxy_pass rules"


def test_readme_file_exists():
    """Test that README.md exists in test/infra."""
    readme_file = "test/infra/README.md"
    assert os.path.exists(readme_file), f"File {readme_file} does not exist"


def test_readme_file_content():
    """Test that README.md contains docker compose usage instructions."""
    readme_file = "test/infra/README.md"
    with open(readme_file, 'r') as f:
        content = f.read()
    
    assert len(content) > 0, "README.md is empty"
    assert len(content.split('\n')) <= 30, "README.md should be 30 lines or less"
    assert 'docker compose up' in content.lower() or 'docker-compose up' in content.lower(), "README.md should mention docker compose up"


def test_version_specified():
    """Test that docker-compose version is specified."""
    compose_file = "test/infra/docker-compose.yml"
    with open(compose_file, 'r') as f:
        content = yaml.safe_load(f)
    
    assert 'version' in content, "docker-compose.yml should specify version"
    version = content['version']
    assert version == '3.9', f"Version should be 3.9, got {version}"
