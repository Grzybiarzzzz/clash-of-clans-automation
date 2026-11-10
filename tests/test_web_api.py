import pytest
from fastapi.testclient import TestClient

from coc_bot.bot_state import BotStateManager
from web.server import app


@pytest.fixture
def client():
    """Create test client with fresh state manager."""
    state = BotStateManager()
    state.update({"running": False, "paused": True, "current_profile": "Farming", "loop_count": 0, "status": "PAUSED"})
    app.state.bot_state = state
    return TestClient(app)


def test_get_state(client):
    """GET /api/state returns current state."""
    response = client.get("/api/state")
    assert response.status_code == 200
    data = response.json()
    assert data["current_profile"] == "Farming"
    assert data["paused"] is True


def test_post_control_pause(client):
    """POST /api/control/pause toggles pause state."""
    # Initially paused
    assert app.state.bot_state.get("paused") is True

    response = client.post("/api/control/pause")
    assert response.status_code == 200
    assert app.state.bot_state.get("paused") is False


def test_put_settings(client):
    """PUT /api/settings updates settings."""
    response = client.put("/api/settings", json={"min_resources": 1500000, "max_th_level": 14})
    assert response.status_code == 200
    assert app.state.bot_state.get("min_resources") == 1500000
    assert app.state.bot_state.get("max_th_level") == 14
