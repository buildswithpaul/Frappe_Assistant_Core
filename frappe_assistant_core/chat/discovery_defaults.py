# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""The Your FAC powers every site shows, unless AR sends its own.

Every user with FAC Chat gets the Your FAC ring and its six powers out of the box. When AR's
capabilities carry a ``discovery`` block (its own wording, order, or the ring switched off),
that block wins.
"""

from frappe import _


def with_default_discovery(capabilities: dict) -> dict:
    """Add the default Your FAC powers to a capabilities response when AR sent none.

    Both capabilities endpoints use this: init on boot, and get_capabilities, which the chat
    page calls again afterwards and whose answer replaces the first one.
    """
    if not capabilities.get("discovery"):
        return {**capabilities, "discovery": default_discovery_capability()}
    return capabilities


def default_discovery_capability() -> dict:
    """The ``capabilities.discovery`` block, in the shape AR sends it, in the user's language."""
    return {
        "progress_enabled": True,
        "powers": [
            {"id": "setup", "label": _("Set up FAC")},
            {"id": "ask", "label": _("Ask your data"), "description": _("Get your first answer")},
            {
                "id": "templates",
                "label": _("Prompt templates"),
                "description": _("Ask a ready-made question"),
            },
            {"id": "knowledge", "label": _("Knowledge"), "description": _("Answers from your own files")},
            {"id": "pages", "label": _("Pages"), "description": _("Keep an answer as a live report")},
            {
                "id": "agents",
                "label": _("Agents"),
                "description": _("Routine work on a schedule"),
                "try_route": "/agents?tab=marketplace",
            },
        ],
    }
