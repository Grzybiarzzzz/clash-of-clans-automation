import tempfile
import os
from coc_bot.bot_state import BotStateManager


def test_get_set_basic():
    """State manager can store and retrieve values."""
    state = BotStateManager()
    state.set("running", True)
    assert state.get("running") is True


def test_get_default():
    """Get returns None for missing keys."""
    state = BotStateManager()
    assert state.get("nonexistent") is None


def test_get_default_value():
    """Get returns default if provided for missing keys."""
    state = BotStateManager()
    assert state.get("nonexistent", "default") == "default"


def test_subscribe_notifies_on_change():
    """Subscribers are notified when state changes."""
    state = BotStateManager()
    notifications = []

    def callback(key, value):
        notifications.append((key, value))

    state.subscribe(callback)
    state.set("loop_count", 42)

    assert len(notifications) == 1
    assert notifications[0] == ("loop_count", 42)


def test_multiple_subscribers():
    """Multiple subscribers all receive notifications."""
    state = BotStateManager()
    results1 = []
    results2 = []

    state.subscribe(lambda k, v: results1.append((k, v)))
    state.subscribe(lambda k, v: results2.append((k, v)))
    state.set("status", "RUNNING")

    assert results1 == [("status", "RUNNING")]
    assert results2 == [("status", "RUNNING")]


def test_unsubscribe():
    """Unsubscribed callbacks no longer receive notifications."""
    state = BotStateManager()
    results = []

    def callback(key, value):
        results.append((key, value))

    state.subscribe(callback)
    state.set("a", 1)
    state.unsubscribe(callback)
    state.set("b", 2)

    assert results == [("a", 1)]


def test_get_all():
    """Get all returns copy of entire state."""
    state = BotStateManager()
    state.set("a", 1)
    state.set("b", 2)

    all_state = state.get_all()
    assert all_state == {"a": 1, "b": 2}

    # Verify it's a copy (modifying doesn't affect internal state)
    all_state["c"] = 3
    assert state.get("c") is None


def test_update_bulk():
    """Update multiple values at once."""
    state = BotStateManager()
    notifications = []
    state.subscribe(lambda k, v: notifications.append((k, v)))

    state.update({"x": 10, "y": 20})

    assert state.get("x") == 10
    assert state.get("y") == 20
    assert len(notifications) == 2


def test_save_load_json():
    """State persists to and loads from JSON file."""
    state = BotStateManager()
    state.set("profile", "Farming")
    state.set("min_resources", 1200000)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        filepath = f.name

    try:
        state.save_to_json(filepath)

        # Load into new state manager
        state2 = BotStateManager()
        state2.load_from_json(filepath)

        assert state2.get("profile") == "Farming"
        assert state2.get("min_resources") == 1200000
    finally:
        os.unlink(filepath)
