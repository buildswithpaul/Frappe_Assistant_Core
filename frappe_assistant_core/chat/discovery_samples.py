# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Sample Did you know tip, What's new story and Your FAC powers, for trying the feature on a test site.

AR is the source of all three. Until AR sends ``tip`` / ``story`` notifications and a
``capabilities.discovery`` block, a test site can set ``"fac_discovery_samples": 1`` in
site_config.json to see them. Off everywhere else: nothing here runs without that key.
"""

import frappe

SAMPLE_TIP_ID = "sample-tip-agents"
SAMPLE_STORY_ID = "sample-story-whats-new"


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


def sample_notifications() -> list[dict]:
    """One tip and one story in the shape AR will send them."""
    return [
        {
            "id": SAMPLE_TIP_ID,
            "display_style": "tip",
            "type": "feature",
            "priority": "normal",
            "title": "Did you know?",
            "message": "An agent can email you overdue invoices every Monday.",
            "highlights": ["Starts from a ready-made template", "About 1 minute to set up"],
            "action_label": "Show me agents",
            "action_route": "/agents?tab=marketplace",
            "feature": "agents",
            "repeat": "daily",
            "dismissible": True,
            "dismissed": False,
            "created_at": "",
        },
        {
            "id": SAMPLE_STORY_ID,
            "display_style": "story",
            "type": "feature",
            "priority": "normal",
            "title": "New in FAC",
            "message": "Three things that are new this month.",
            "slides": [
                {
                    "title": "⚡ Agents do the routine work",
                    "message": "Pick a template and FAC checks, emails or updates things for you on a schedule.",
                    "feature": "agents",
                },
                {
                    "title": "📚 Answers from your own files",
                    "message": "Upload a price list or a policy to Knowledge and FAC answers from it.",
                    "feature": "knowledge",
                },
                {
                    "title": "📊 Save any answer as a Page",
                    "message": "Ask for numbers, then keep them as a live Page you can share as PDF.",
                    "feature": "pages",
                    "action_label": "Try it",
                    "action_route": "/chat",
                },
            ],
            "dismissible": True,
            "dismissed": False,
            "created_at": "",
        },
    ]


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
