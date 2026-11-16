"""Telling the local web GUI apart from other websites.

The server listens on loopback only, but that does not stop a web page open in the user's
browser from sending requests to http://localhost:8000. Browsers attach the sending page's
``Origin`` to every WebSocket handshake and to every POST/PUT, so requests that change
something are accepted only when that origin is this machine. Clients that are not
browsers (curl, scripts) send no Origin and are allowed.
"""

from urllib.parse import urlsplit

LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


def is_allowed_origin(origin) -> bool:
    """True for a missing Origin header and for origins served from this machine."""
    if origin is None:
        return True
    try:
        return urlsplit(origin).hostname in LOCAL_HOSTS
    except ValueError:
        return False
