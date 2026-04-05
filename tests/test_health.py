from fastapi.testclient import TestClient

def test_health_check(client: TestClient):
    """
    Test the health check endpoint.
    Ensures the API is alive and reachable.
    """
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "message": "FastAPI Task Management API is healthy"}

def test_root_path(client: TestClient):
    """
    Test the root path redirects or returns a message.
    """
    response = client.get("/")
    assert response.status_code == 200
    assert "status" in response.json()
