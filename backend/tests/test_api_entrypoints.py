import re

from fastapi.testclient import TestClient

from server import app


client = TestClient(app)


def test_demo_login_accepts_only_fixed_account():
    success = client.post(
        "/api/login",
        json={"username": "admin", "password": "123123"},
    )
    assert success.status_code == 200
    payload = success.json()
    assert payload["success"] is True
    assert payload["username"] == "admin"
    assert re.fullmatch(r"[a-f0-9]{32}", payload["token"])

    rejected = client.post(
        "/api/login",
        json={"username": "admin", "password": "wrong"},
    )
    assert rejected.status_code == 401
    assert rejected.json()["success"] is False


def test_roles_endpoint_returns_all_eight_roles():
    response = client.get("/api/roles")
    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert len(payload["roles"]) == 8
    assert len({role["key"] for role in payload["roles"]}) == 8


def test_text_resume_endpoint_is_available():
    response = client.post(
        "/api/resume/parse-text",
        json={"content": "熟悉 Python、FastAPI、SQL 和数据分析"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert "Python" in payload["skills"]
    assert payload["suggested_role"]


def test_multipart_resume_endpoint_exists_and_validates_file_type():
    response = client.post(
        "/api/upload/resume",
        files={"file": ("resume.txt", b"plain text", "text/plain")},
    )
    assert response.status_code == 200
    assert response.status_code != 404
    assert response.json() == {"success": False, "message": "仅支持 PDF 文件"}


def test_backend_root_no_longer_serves_frontend():
    response = client.get("/")
    assert response.status_code == 404
