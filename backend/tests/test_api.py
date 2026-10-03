import importlib

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.auth import issue_token
from app.services.store import get_store
import app.services.store as store_module


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "app_mode", "local")
    monkeypatch.setattr(settings, "database_path", str(tmp_path / "test.db"))
    monkeypatch.setattr(settings, "local_storage_path", str(tmp_path / "uploads"))
    monkeypatch.setattr(settings, "jwt_secret", "test-only-secret-that-is-long-enough")
    store_module._store = None
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client
    store_module._store = None


def account(client, email="person@example.com"):
    result = client.post("/register", json={"email": email, "password": "demo-password-123"})
    assert result.status_code == 201
    return {"Authorization": f"Bearer {result.json()['access_token']}"}


def add_profile(client, headers, dietary="vegetarian", goal="balanced"):
    return client.put("/profile", headers=headers, json={
        "name": "Demo Person", "age": 25, "height_cm": 170, "weight_kg": 65,
        "activity_level": "moderate", "dietary_preference": dietary,
        "goal": goal, "allergies": []
    })


def test_registration_duplicate_and_login(client):
    headers = account(client)
    duplicate = client.post("/register", json={"email": "person@example.com", "password": "demo-password-123"})
    assert duplicate.status_code == 409
    login = client.post("/login", json={"email": "person@example.com", "password": "demo-password-123"})
    assert login.status_code == 200
    bad_login = client.post("/login", json={"email": "person@example.com", "password": "wrong-password"})
    assert bad_login.status_code == 401
    assert headers["Authorization"].startswith("Bearer ")


def test_unauthorized_profile_is_rejected(client):
    assert client.get("/profile").status_code == 401


@pytest.mark.parametrize("preference", ["vegetarian", "vegan", "general"])
def test_generation_honors_dietary_preference(client, preference):
    headers = account(client)
    assert add_profile(client, headers, preference).status_code == 200
    plan = client.post("/generate-plan", headers=headers)
    assert plan.status_code == 201
    assert plan.json()["source"] == "rule-based"
    if preference == "vegan":
        assert "tofu" in plan.json()["dinner"].lower() or "lentil" in plan.json()["dinner"].lower()
    assert plan.json()["educational_notice"].startswith("Educational")


def test_user_cannot_read_or_delete_another_users_plan(client):
    headers_a = account(client, "a@example.com")
    headers_b = account(client, "b@example.com")
    add_profile(client, headers_a)
    plan_id = client.post("/generate-plan", headers=headers_a).json()["plan_id"]
    assert client.get(f"/plans/{plan_id}", headers=headers_b).status_code == 404
    assert client.delete(f"/plans/{plan_id}", headers=headers_b).status_code == 404
    assert len(client.get("/plans", headers=headers_a).json()) == 1


def test_user_file_upload_download_and_isolation(client):
    headers_a = account(client, "file-a@example.com")
    headers_b = account(client, "file-b@example.com")
    png_demo = b"\x89PNG\r\n\x1a\n" + b"demo-image"
    uploaded = client.post("/upload", headers=headers_a, files={"file": ("meal.png", png_demo, "image/png")})
    assert uploaded.status_code == 201
    file_id = uploaded.json()["file_id"]
    assert client.get(f"/files/{file_id}/download", headers=headers_a).content == png_demo
    assert client.get(f"/files/{file_id}/download", headers=headers_b).status_code == 404
    invalid = client.post("/upload", headers=headers_a, files={"file": ("meal.txt", b"text", "text/plain")})
    assert invalid.status_code == 415


def test_missing_profile_blocks_generation(client):
    headers = account(client)
    assert client.post("/generate-plan", headers=headers).status_code == 400


def test_database_failure_returns_safe_service_error(client):
    class BrokenStore:
        def list_plans(self, user_id):
            raise RuntimeError("provider credentials must not be returned to clients")

    app.dependency_overrides[get_store] = lambda: BrokenStore()
    try:
        headers = {"Authorization": f"Bearer {issue_token('demo-user', 'demo@example.com')}"}
        response = client.get("/plans", headers=headers)
    finally:
        app.dependency_overrides.pop(get_store, None)
    assert response.status_code == 503
    assert "credentials" not in response.text
