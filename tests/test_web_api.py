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


# --- requests from other websites ------------------------------------------------------------
# The server only listens on loopback, but any web page open in the user's browser can still
# send requests to http://localhost:8000. Browsers attach the page's Origin to those requests.


@pytest.mark.parametrize("origin", ["http://evil.example", "https://localhost.evil.example", "null"])
def test_a_page_from_another_site_cannot_start_the_bot(client, origin):
    response = client.post("/api/control/start", headers={"Origin": origin})

    assert response.status_code == 403
    assert app.state.bot_state.get("running") is False


def test_a_page_from_another_site_cannot_change_settings(client):
    response = client.put("/api/settings", json={"min_resources": 1}, headers={"Origin": "http://evil.example"})

    assert response.status_code == 403
    assert app.state.bot_state.get("min_resources") is None


@pytest.mark.parametrize(
    "origin", ["http://localhost:8000", "http://127.0.0.1:8000", "http://localhost:5173", "http://[::1]:8000"]
)
def test_the_local_web_gui_can_control_the_bot(client, origin):
    response = client.post("/api/control/start", headers={"Origin": origin})

    assert response.status_code == 200
    assert app.state.bot_state.get("running") is True


def test_reading_the_state_needs_no_origin(client):
    assert client.get("/api/state", headers={"Origin": "http://evil.example"}).status_code == 200


def test_a_page_from_another_site_cannot_open_the_control_socket(client):
    from starlette.websockets import WebSocketDisconnect

    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws", headers={"Origin": "http://evil.example"}):
            pass


def test_the_local_web_gui_can_open_the_control_socket(client):
    with client.websocket_connect("/ws", headers={"Origin": "http://localhost:8000"}) as websocket:
        assert websocket.receive_json()["type"] == "state_update"
