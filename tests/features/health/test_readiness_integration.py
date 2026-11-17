import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration


def test_ready_against_real_postgres(database: str, client: TestClient) -> None:
    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}
