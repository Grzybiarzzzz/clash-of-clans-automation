"""
WebSocket handler for real-time state sync.
"""

import asyncio
import queue
from typing import Set, Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect


router = APIRouter()


class ConnectionManager:
    """Manages active WebSocket connections with thread-safe broadcasting."""

    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self._lock = asyncio.Lock()
        self._event_loop: Optional[asyncio.AbstractEventLoop] = None
        self._message_queue: queue.Queue = queue.Queue()
        self._queue_processor_running = False

    def set_event_loop(self, loop: asyncio.AbstractEventLoop):
        """Store reference to the uvicorn event loop for cross-thread broadcasts."""
        self._event_loop = loop

    async def connect(self, websocket: WebSocket):
        """Accept and register a new connection."""
        await websocket.accept()
        async with self._lock:
            self.active_connections.add(websocket)

    async def disconnect(self, websocket: WebSocket):
        """Remove a connection."""
        async with self._lock:
            self.active_connections.discard(websocket)

    async def broadcast(self, message: dict):
        """Send message to all connected clients."""
        async with self._lock:
            connections = self.active_connections.copy()

        for connection in connections:
            try:
                await connection.send_json(message)
            except Exception:
                await self.disconnect(connection)

    def broadcast_threadsafe(self, message: dict):
        """
        Thread-safe broadcast - can be called from any thread.
        Schedules the broadcast in the uvicorn event loop.
        """
        if self._event_loop is None:
            return

        try:
            # Schedule the async broadcast in the uvicorn event loop
            self._event_loop.call_soon_threadsafe(
                lambda: asyncio.create_task(self.broadcast(message))
            )
        except RuntimeError:
            # Event loop closed or not running
            pass


manager = ConnectionManager()


def setup_state_listener(state_manager):
    """
    Subscribe to state changes and broadcast to WebSocket clients.
    Called once when server starts.
    """
    def on_state_change(key: str, value):
        # Handle different log types specially
        if key == "log":
            message = {"type": "log", "data": value}
        elif key == "debug_log":
            message = {"type": "debug_log", "data": value}
        elif key == "ocr_log":
            message = {"type": "ocr_log", "data": value}
        else:
            # Create broadcast message for state updates
            message = {"type": "state_update", "data": {key: value}}

        # Use thread-safe broadcast (works from bot thread or any other thread)
        manager.broadcast_threadsafe(message)

    state_manager.subscribe(on_state_change)


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time state sync."""
    # Refresh the loop when reconnecting after a server/test-client restart.
    manager.set_event_loop(asyncio.get_running_loop())

    await manager.connect(websocket)

    # Send initial state
    state = websocket.app.state.bot_state
    await websocket.send_json({
        "type": "state_update",
        "data": state.get_all()
    })

    try:
        while True:
            # Receive messages from client
            data = await websocket.receive_json()

            if data.get("type") == "control":
                action = data.get("data", {}).get("action")
                if action == "start":
                    state.set("running", True)
                    state.set("paused", False)
                elif action == "pause":
                    current = state.get("paused", True)
                    state.set("paused", not current)
                elif action == "stop":
                    state.set("running", False)
                    state.set("paused", True)

            elif data.get("type") == "setting_change":
                key = data.get("data", {}).get("key")
                value = data.get("data", {}).get("value")
                if key:
                    # Special handling for active_storage_preset - copy preset values to global settings
                    if key == "active_storage_preset":
                        import json
                        try:
                            with open('data/bot_settings.json', 'r', encoding='utf-8') as f:
                                settings = json.load(f)

                            if 'storage_presets' in settings and value in settings['storage_presets']:
                                preset = settings['storage_presets'][value]

                                # Update global settings with preset values
                                settings['active_storage_preset'] = value
                                settings['max_gold_storage'] = preset['max_gold_storage']
                                settings['max_elixir_storage'] = preset['max_elixir_storage']
                                settings['max_dark_elixir_storage'] = preset['max_dark_elixir_storage']
                                settings['max_bb_gold_storage'] = preset.get('max_bb_gold_storage', 5000000)
                                settings['max_bb_elixir_storage'] = preset.get('max_bb_elixir_storage', 5000000)

                                # Save to JSON
                                with open('data/bot_settings.json', 'w', encoding='utf-8') as f:
                                    json.dump(settings, f, indent=2)

                                # Update state manager with all changed values
                                state.set('active_storage_preset', value)
                                state.set('max_gold_storage', preset['max_gold_storage'])
                                state.set('max_elixir_storage', preset['max_elixir_storage'])
                                state.set('max_dark_elixir_storage', preset['max_dark_elixir_storage'])
                                state.set('max_bb_gold_storage', preset.get('max_bb_gold_storage', 5000000))
                                state.set('max_bb_elixir_storage', preset.get('max_bb_elixir_storage', 5000000))
                        except Exception as e:
                            print(f"[WebSocket] Error applying storage preset: {e}")
                    else:
                        state.set(key, value)

    except WebSocketDisconnect:
        pass  # Normal disconnect, no need to log
    except ConnectionResetError:
        pass  # Client closed connection abruptly (refresh, sleep, etc.)
    except Exception:
        pass  # Catch any other connection errors silently
    finally:
        await manager.disconnect(websocket)
