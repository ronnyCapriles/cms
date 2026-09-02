"""Cache-busting URLs for the admin's own CSS and JS.

WhiteNoise serves /static/ with a year-long max-age, which is fine for Vite's
content-hashed filenames but not for these two, whose names never change.
"""
from __future__ import annotations

import hashlib
import os
from functools import lru_cache

from django.contrib.staticfiles import finders
from django.templatetags.static import static


@lru_cache(maxsize=32)
def _digest(path: str, mtime_ns: int, size: int) -> str:
    """mtime and size are cache keys, not inputs: an edited file misses the
    cache without a restart."""
    with open(path, "rb") as handle:
        return hashlib.sha1(handle.read()).hexdigest()[:12]


def asset_url(path: str) -> str:
    """`static(path)` with a digest of the file appended. Falls back to the
    plain URL when the file is not on disk."""
    absolute = finders.find(path)
    if not absolute:
        return static(path)
    stat = os.stat(absolute)
    return f"{static(path)}?v={_digest(absolute, stat.st_mtime_ns, stat.st_size)}"
