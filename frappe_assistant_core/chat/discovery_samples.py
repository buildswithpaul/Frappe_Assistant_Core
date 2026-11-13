# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Sample Your FAC powers, for trying the ring on a test site.

AR is the source of the powers; daily tips ship with FAC itself, in dailyTips.js. Until AR sends a
``capabilities.discovery`` block, a test site can set ``"fac_discovery_samples": 1`` in
site_config.json to see them. Off everywhere else: nothing here runs without that key.
"""

import frappe


def samples_enabled() -> bool:
    return bool(frappe.conf.get("fac_discovery_samples"))


def with_sample_discovery(capabilities: dict) -> dict:
    """Add the sample Your FAC powers to a capabilities response when AR sent none.

    Both capabilities endpoints use this: init on boot, and get_capabilities, which the chat
    page calls again afterwards and whose answer replaces the first one.
    """
    if samples_enabled() and not capabilities.get("discovery"):
        return {**capabilities, "discovery": sample_discovery_capability()}
    return capabilities


def sample_discovery_capability() -> dict:
    """The ``capabilities.discovery`` block, in the shape AR will send it."""
    return {
        "progress_enabled": True,
        "powers": [
            {"id": "setup", "label": "Set up FAC"},
            {"id": "ask", "label": "Ask your data", "description": "Get your first answer"},
            {"id": "templates", "label": "Prompt templates", "description": "Pin a saved question"},
            {"id": "knowledge", "label": "Knowledge", "description": "Answers from your own files"},
            {"id": "pages", "label": "Pages", "description": "Keep an answer as a live report"},
            {
                "id": "agents",
                "label": "Agents",
                "description": "Routine work on a schedule",
                "try_route": "/agents?tab=marketplace",
            },
        ],
    }
