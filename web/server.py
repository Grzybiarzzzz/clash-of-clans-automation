"""
FastAPI server for web GUI.
Provides REST API and WebSocket for real-time state sync.
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path for standalone execution
_parent = Path(__file__).parent.parent
if str(_parent) not in sys.path:
    sys.path.insert(0, str(_parent))

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from web.routes.api import router as api_router
from web.routes.ws import router as ws_router, setup_state_listener


app = FastAPI(title="CoC Bot Control API")

# Register API routes
app.include_router(api_router)
app.include_router(ws_router)

# Path to built frontend
FRONTEND_DIR = Path(__file__).parent / "frontend" / "dist"


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}


# Serve static files if frontend is built
if FRONTEND_DIR.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIR / "assets"), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """Serve Vue SPA - all non-API routes return index.html."""
        frontend_root = FRONTEND_DIR.resolve()
        file_path = (frontend_root / full_path).resolve()
        try:
            file_path.relative_to(frontend_root)
        except ValueError:
            raise HTTPException(status_code=404, detail="Not found")
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        # Return index.html with no-cache headers to ensure updates are seen
        return FileResponse(
            FRONTEND_DIR / "index.html",
            headers={"Cache-Control": "no-cache, no-store, must-revalidate"}
        )


def _suppress_connection_errors(loop, context):
    """Suppress noisy but harmless connection reset errors on Windows."""
    exception = context.get('exception')
    if isinstance(exception, ConnectionResetError):
        return  # Silently ignore - happens when client disconnects abruptly
    if isinstance(exception, OSError) and exception.errno == 10054:
        return  # WinError 10054 - connection reset by remote host
    # For other exceptions, use default handler
    loop.default_exception_handler(context)


def start_web_server(
    state_manager,  # BotStateManager
    host: str = "127.0.0.1",
    port: int = 8000
) -> None:
    """
    Start the web server.
    Called from main.py in a background thread.
    """
    # Store state manager for route access
    app.state.bot_state = state_manager

    # Set up state change listener for WebSocket broadcasts
    setup_state_listener(state_manager)

    print(f"[Web] Starting server at http://{host}:{port}")

    # Run uvicorn with custom exception handler to suppress connection reset errors
    config = uvicorn.Config(app, host=host, port=port, log_level="warning")
    server = uvicorn.Server(config)

    # Create event loop with custom exception handler
    loop = asyncio.new_event_loop()
    loop.set_exception_handler(_suppress_connection_errors)
    asyncio.set_event_loop(loop)

    try:
        loop.run_until_complete(server.serve())
    finally:
        loop.close()


if __name__ == "__main__":
    # For testing without bot
    from bot_state import BotStateManager
    state = BotStateManager()
    state.update({
        "running": False,
        "paused": True,
        "status": "PAUSED",
        "current_profile": "Farming",
        "loop_count": 0
    })
    app.state.bot_state = state
    setup_state_listener(state)
    print("[Web] Starting server at http://127.0.0.1:8000")
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")
