import pytest
from fastapi.testclient import TestClient

from coc_bot.bot_state import BotStateManager
from web.server import app
from web.routes.ws import setup_state_listener


@pytest.fixture
def state():
    """Create fresh state manager."""
    s = BotStateManager()
    s.update({"running": False, "paused": True, "loop_count": 0})
    app.state.bot_state = s
    setup_state_listener(s)
    return s


def test_websocket_connect(state):
    """WebSocket connection succeeds and receives initial state."""
    client = TestClient(app)
    with client.websocket_connect("/ws") as websocket:
        # Should receive initial state on connect
        data = websocket.receive_json()
        assert data["type"] == "state_update"
        assert "paused" in data["data"]


def test_websocket_receives_state_changes(state):
    """WebSocket receives broadcasts when state changes."""
    client = TestClient(app)
    with client.websocket_connect("/ws") as websocket:
        # Consume initial state message
        websocket.receive_json()

        # Change state (simulating Tkinter or bot update)
        state.set("loop_count", 42)

        # Should receive the update
        data = websocket.receive_json()
        assert data["type"] == "state_update"
        assert data["data"]["loop_count"] == 42


def test_websocket_send_command(state):
    """WebSocket can send control commands."""
    client = TestClient(app)
    with client.websocket_connect("/ws") as websocket:
        # Consume initial state
        websocket.receive_json()

        # Send pause command
        websocket.send_json({"type": "control", "data": {"action": "pause"}})

        # State should be updated
        # (Give brief time for processing)
        import time

        time.sleep(0.1)
        assert state.get("paused") is False  # Toggled from True
