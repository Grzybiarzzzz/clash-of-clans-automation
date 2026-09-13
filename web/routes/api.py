"""
REST API endpoints for bot control.
"""

from typing import Any, Dict

from fastapi import APIRouter, Request


router = APIRouter(prefix="/api", tags=["api"])


@router.get("/state")
async def get_state(request: Request) -> Dict[str, Any]:
    """Get full current state."""
    state = request.app.state.bot_state
    return state.get_all()


@router.post("/control/start")
async def control_start(request: Request) -> Dict[str, str]:
    """Start the bot."""
    state = request.app.state.bot_state
    state.set("running", True)
    state.set("paused", False)
    state.set("status", "RUNNING")
    return {"status": "started"}


@router.post("/control/pause")
async def control_pause(request: Request) -> Dict[str, Any]:
    """Toggle pause state."""
    state = request.app.state.bot_state
    current = state.get("paused", True)
    state.set("paused", not current)
    state.set("status", "PAUSED" if not current else "RUNNING")
    return {"paused": not current}


@router.post("/control/stop")
async def control_stop(request: Request) -> Dict[str, str]:
    """Stop the bot."""
    state = request.app.state.bot_state
    state.set("running", False)
    state.set("paused", True)
    state.set("status", "STOPPED")
    return {"status": "stopped"}


@router.post("/profile/{name}")
async def switch_profile(request: Request, name: str) -> Dict[str, str]:
    """Switch to a different profile."""
    state = request.app.state.bot_state
    state.set("current_profile", name)
    return {"profile": name}


@router.put("/settings")
async def update_settings(request: Request, settings: Dict[str, Any]) -> Dict[str, str]:
    """Update settings (partial update)."""
    state = request.app.state.bot_state
    state.update(settings)
    return {"status": "updated"}
