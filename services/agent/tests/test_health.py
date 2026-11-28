from fastapi.testclient import TestClient

from agent_service import __version__
from agent_service.app import app


def test_health_reports_ok_and_version():
    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": __version__}


def test_root_opens_the_api_docs():
    response = TestClient(app).get("/", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"] == "/docs"
