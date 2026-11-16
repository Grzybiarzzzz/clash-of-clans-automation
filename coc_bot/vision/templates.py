"""In-memory cache of the reference images used for template matching."""

import cv2

_cache = {}


def load_template(path):
    """The BGR image at ``path``, read from disk on first use. None when it cannot be read.

    A missing file is not remembered, so a template captured while the bot is running is
    picked up on the next call. Treat the returned array as read-only: it is shared.
    """
    template = _cache.get(path)
    if template is None:
        template = cv2.imread(path)
        if template is not None:
            _cache[path] = template
    return template


def clear_cache():
    _cache.clear()
