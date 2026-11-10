"""
Shared state manager for bot control.
Allows multiple GUIs (Tkinter, Web) to share and sync state.
"""

import json
import threading
from typing import Any, Callable, Dict, List


class BotStateManager:
    """Thread-safe state manager with pub/sub support."""

    def __init__(self):
        self._state: Dict[str, Any] = {}
        self._subscribers: List[Callable[[str, Any], None]] = []
        self._lock = threading.RLock()

    def get(self, key: str, default: Any = None) -> Any:
        """Get a value from state."""
        with self._lock:
            return self._state.get(key, default)

    def get_all(self) -> Dict[str, Any]:
        """Get a copy of the entire state."""
        with self._lock:
            return self._state.copy()

    def set(self, key: str, value: Any) -> None:
        """Set a value in state and notify subscribers."""
        with self._lock:
            self._state[key] = value
            subscribers = self._subscribers.copy()

        # Notify outside lock to prevent deadlocks
        for callback in subscribers:
            try:
                callback(key, value)
            except Exception as e:
                print(f"[BotState] Subscriber error: {e}")

    def update(self, data: Dict[str, Any]) -> None:
        """Update multiple values at once, notifying for each."""
        for key, value in data.items():
            self.set(key, value)

    def subscribe(self, callback: Callable[[str, Any], None]) -> None:
        """Subscribe to state changes."""
        with self._lock:
            self._subscribers.append(callback)

    def unsubscribe(self, callback: Callable[[str, Any], None]) -> None:
        """Unsubscribe from state changes."""
        with self._lock:
            if callback in self._subscribers:
                self._subscribers.remove(callback)

    def save_to_json(self, filepath: str) -> None:
        """Save current state to JSON file."""
        with self._lock:
            state_copy = self._state.copy()

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(state_copy, f, indent=2)

    def load_from_json(self, filepath: str) -> None:
        """Load state from JSON file."""
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)

        with self._lock:
            self._state = data
