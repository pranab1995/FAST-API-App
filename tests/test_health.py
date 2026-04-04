from fastapi import status

# =============================================================================
# tests/test_health.py
#
# PURPOSE:
#   Integration tests for the health check endpoints.
#
# USAGE:
#   pytest tests/test_health.py
# =============================================================================

def test_root_health(client):
    """
    Test the root GET / endpoint returns 200 Healthy.
    """
    response = client.get("/")
    assert response.status_code == status.HTTP_200_OK
    
    data = response.json()
    assert data["status"] == "healthy"
    assert "service" in data
    assert "version" in data


def test_detailed_health(client):
    """
    Test the detailed GET /health endpoint.
    """
    response = client.get("/health")
    assert response.status_code == status.HTTP_200_OK
    
    data = response.json()
    assert data["status"] == "healthy"
    # The detailed health check should have a 'debug' key
    assert "debug" in data
