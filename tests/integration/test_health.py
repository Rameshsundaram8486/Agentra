from fastapi.testclient import TestClient
from pydantic import SecretStr

from app import __version__
from app.infrastructure.settings import Settings
from app.main import create_app


def test_health_reports_ok_when_database_is_reachable(test_settings: Settings) -> None:
    with TestClient(create_app(test_settings)) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok", "version": __version__}


def test_health_reports_unavailable_database_without_leaking_credentials(test_settings: Settings) -> None:
    unreachable = "postgresql+psycopg://agentra:not-a-real-password@127.0.0.1:1/agentra_test"
    settings = test_settings.model_copy(update={"database_url": SecretStr(unreachable)})

    with TestClient(create_app(settings)) as client:
        response = client.get("/health")

    assert response.status_code == 503
    assert response.json()["database"] == "unavailable"
    assert "not-a-real-password" not in response.text
