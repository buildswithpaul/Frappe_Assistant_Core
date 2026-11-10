# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""The FAC Chat demo video: a short YouTube video the Desk shows before chat is switched on.

There is no separate site to host it, so it lives on YouTube. The link is set once here for
every site; a site can point elsewhere with ``fac_demo_video_url`` in site_config.json (for
example to test a new cut). Only a YouTube link is accepted, and the page builds its own
watch/embed URLs from the video id, so nothing else ever reaches an iframe.
"""

import re
from urllib.parse import parse_qs, urlparse

import frappe

# Set when the 30-second demo is published. Empty = no "Watch the demo" button anywhere.
DEMO_VIDEO_URL = ""

_VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
_LONG_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "youtube-nocookie.com",
    "www.youtube-nocookie.com",
}
_SHORT_HOSTS = {"youtu.be", "www.youtu.be"}


def youtube_id(url: str | None) -> str | None:
    """The 11-character video id of a YouTube watch, share, embed or Shorts link; else None."""
    if not url or not isinstance(url, str):
        return None
    try:
        parsed = urlparse(url.strip())
    except ValueError:
        return None
    if parsed.scheme not in ("http", "https"):
        return None
    host = (parsed.hostname or "").lower()
    parts = [p for p in parsed.path.split("/") if p]
    candidate = None
    if host in _SHORT_HOSTS:
        candidate = parts[0] if parts else None
    elif host in _LONG_HOSTS:
        if parts[:1] == ["watch"]:
            candidate = (parse_qs(parsed.query).get("v") or [None])[0]
        elif len(parts) >= 2 and parts[0] in ("embed", "shorts", "live"):
            candidate = parts[1]
    return candidate if candidate and _VIDEO_ID.match(candidate) else None


def demo_video() -> dict | None:
    """``{"url", "embed"}`` for the demo video, or None when none is set (or the link is not YouTube)."""
    configured = frappe.conf.get("fac_demo_video_url") or DEMO_VIDEO_URL
    video_id = youtube_id(configured)
    if not video_id:
        return None
    return {
        "url": f"https://www.youtube.com/watch?v={video_id}",
        "embed": f"https://www.youtube-nocookie.com/embed/{video_id}?rel=0",
    }
