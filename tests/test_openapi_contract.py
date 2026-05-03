"""Smoke test: every /api/* route has a typed JSON response schema in OpenAPI."""
import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


def test_openapi_loads(client):
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    data = resp.json()
    assert "paths" in data
    assert "components" in data


def test_api_routes_exist(client):
    resp = client.get("/openapi.json")
    paths = resp.json().get("paths", {})
    api_paths = [p for p in paths if p.startswith("/api/")]
    assert len(api_paths) > 0, "No /api/* routes found — check router prefix includes in main.py"


def test_api_routes_have_typed_responses(client):
    resp = client.get("/openapi.json")
    schema = resp.json()
    paths = schema.get("paths", {})

    failures = []
    for path, methods in paths.items():
        if not path.startswith("/api/"):
            continue
        for method, operation in methods.items():
            if method not in ("get", "post", "put", "patch", "delete"):
                continue
            responses = operation.get("responses", {})
            ok_resp = responses.get("200") or responses.get("201")
            if ok_resp is None:
                continue
            content = ok_resp.get("content", {})
            json_content = content.get("application/json")
            if json_content is None:
                # Non-JSON response (e.g. file download) — skip
                continue
            schema_def = json_content.get("schema", {})
            has_type = bool(
                schema_def.get("$ref")
                or schema_def.get("properties")
                or schema_def.get("allOf")
                or schema_def.get("items")
            )
            if not has_type:
                failures.append(f"{method.upper()} {path}")

    assert not failures, (
        "API routes missing typed response schemas:\n" + "\n".join(failures)
    )
