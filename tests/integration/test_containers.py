"""Container health: the running Neo4j, FastAPI and Nginx services answer, through the same paths users take."""

import json
import os
import subprocess

import httpx
import pytest

from app.config import get_settings
from app.database import GraphStore

pytestmark = pytest.mark.integration
BASE = os.environ.get("CINEGRAPH_URL", "http://127.0.0.1:18080")


@pytest.fixture(scope="module")
def http():
    with httpx.Client(base_url=BASE, timeout=10) as client:
        yield client


def test_fastapi_is_live_and_ready_behind_nginx(http):
    assert http.get("/health/live").json() == {"status": "alive"}
    ready = http.get("/health/ready")
    assert ready.status_code == 200 and ready.json() == {"status": "ready"}
    assert ready.headers.get("x-frame-options") == "SAMEORIGIN", "the response passed through the Nginx proxy"


def test_swagger_and_openapi_are_served(http):
    assert http.get("/docs").status_code == 200
    paths = http.get("/openapi.json").json()["paths"]
    assert "/api/movies/{movie_id}/path/{other_id}" in paths and "/api/ask" in paths


def test_neo4j_answers_over_bolt():
    store = GraphStore(get_settings())
    try:
        assert store.healthy()
        assert store.read("CALL dbms.components() YIELD name RETURN name")[0]["name"] == "Neo4j Kernel"
    finally:
        store.close()


def test_docker_reports_every_service_healthy():
    try:
        output = subprocess.run(
            ["docker", "compose", "ps", "--format", "json"], capture_output=True, text=True, check=True, timeout=20
        ).stdout
    except (FileNotFoundError, subprocess.CalledProcessError) as error:
        pytest.fail(f"docker compose is not available: {error}")
    services = [json.loads(line) for line in output.splitlines() if line.strip()]
    health = {service["Service"]: service.get("Health") for service in services}
    assert health == {"neo4j": "healthy", "api": "healthy", "nginx": "healthy"}
