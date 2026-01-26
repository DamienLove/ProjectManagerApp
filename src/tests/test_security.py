import sys
import os
from unittest.mock import MagicMock
import pytest
from fastapi.testclient import TestClient

# Mock firebase_admin before importing remote_agent
# This is crucial to avoid side effects during import
sys.modules["firebase_admin"] = MagicMock()
sys.modules["firebase_admin.credentials"] = MagicMock()
sys.modules["firebase_admin.firestore"] = MagicMock()

# We also need to mock cloudflared check if it runs on import?
# Looking at remote_agent.py:
# _tunnel: Optional[CloudflareTunnel] = None
# It doesn't start automatically.

# Add src to sys.path to allow importing remote_agent
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Now import the app
from remote_agent import app, REMOTE_ACCESS_TOKEN

# Override the token for testing
import remote_agent
remote_agent.REMOTE_ACCESS_TOKEN = "test-secret-token"

client = TestClient(app)

def test_health_no_token():
    """Test that requests without token fail."""
    response = client.get("/api/health")
    assert response.status_code == 401
    assert response.json() == {"detail": "Unauthorized"}

def test_health_invalid_token():
    """Test that requests with invalid token fail."""
    headers = {"X-Omni-Token": "wrong-token"}
    response = client.get("/api/health", headers=headers)
    assert response.status_code == 401
    assert response.json() == {"detail": "Unauthorized"}

def test_health_valid_token():
    """Test that requests with valid token succeed."""
    headers = {"X-Omni-Token": "test-secret-token"}
    response = client.get("/api/health", headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

def test_health_valid_token_bearer():
    """Test that requests with valid Bearer token succeed."""
    headers = {"Authorization": "Bearer test-secret-token"}
    response = client.get("/api/health", headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
