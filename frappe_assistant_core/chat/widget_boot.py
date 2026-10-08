# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Tell the Desk where the built widget lives.

The widget is a Vite build with hashed file names, so its entry URL is only
known from the build manifest. Desk boot carries it to `widget_loader.js`.
A site whose frontend was never built gets no widget — never an error.
"""

import json
import os

import frappe

ASSET_BASE = "/assets/frappe_assistant_core/chat/widget-app/"
ENTRY_KEY = "src/widget/main.js"
MANIFEST_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "public", "chat", "widget-app", ".vite", "manifest.json"
)

# Boot runs on every Desk load; re-read only when a rebuild changed the file.
_cache: dict = {}


def _stylesheets(manifest: dict) -> list[str]:
    """Collect every stylesheet in first-seen order.

    With `cssCodeSplit: false` Vite emits the stylesheet as its own record
    (`"style.css": {"file": "assets/style.<hash>.css"}`); a split build lists
    them under each record's `css` array. Accept both, and skip anything that
    is not a string: a malformed manifest must never reach Desk boot.
    """
    css: list[str] = []
    for record in manifest.values():
        if not isinstance(record, dict):
            continue
        listed = record.get("css")
        found = [h for h in listed if isinstance(h, str)] if isinstance(listed, list) else []
        file = record.get("file")
        if isinstance(file, str) and file.endswith(".css"):
            found.append(file)
        for href in found:
            if href not in css:
                css.append(href)
    return css


def widget_entry(manifest_path: str | None = None) -> dict | None:
    path = manifest_path or MANIFEST_PATH
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        return None
    cached = _cache.get(path)
    if cached and cached[0] == mtime:
        return cached[1]
    try:
        # `path` is a module constant or a test fixture — never request data.
        with open(path) as fh:  # nosemgrep: frappe-security-file-traversal
            manifest = json.load(fh)
        entry = manifest[ENTRY_KEY]["file"]
        if not isinstance(entry, str) or not entry:
            return None
        value = {"entry": ASSET_BASE + entry, "css": [ASSET_BASE + c for c in _stylesheets(manifest)]}
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return None
    _cache[path] = (mtime, value)
    return value


def extend_bootinfo(bootinfo, manifest_path: str | None = None) -> None:
    # Frappe does not guard boot hooks: an exception here would break Desk for everyone.
    try:
        entry = widget_entry(manifest_path)
        if entry:
            bootinfo.fac_widget = entry
    except Exception:
        frappe.logger("frappe_assistant_core").warning("FAC widget boot info skipped", exc_info=True)
