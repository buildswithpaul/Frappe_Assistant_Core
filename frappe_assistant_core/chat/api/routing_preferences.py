# Copyright (c) 2025 Paul Clinton
# For license information, please see license.txt

"""Routing preferences, proxied to FAC Cloud.

The caller's identity is derived here from `frappe.session.user`, never read
from the payload: AR authenticates the workspace, not the member, so this is
the hop where "which member is asking" is actually established.
"""

import frappe
from frappe import _

from frappe_assistant_core.chat.api.auth import _ar_user_id

_STATUSES = ("active", "suspended")
# Learning vs live. `off` is not here: that is the platform kill switch on the
# AR side, not a state this workspace can put its own rule into.
_RULE_MODES = ("shadow", "on")
_MATCH_KINDS = ("doctype", "keyword", "task_type")
_SCOPES = ("Tenant",)  # personal rules are not open yet — see create()


def _client():
    from frappe_assistant_core.chat.fac_cloud_client import get_fac_cloud_client

    client = get_fac_cloud_client()
    if not client:
        frappe.throw(_("Not connected to FAC Cloud"))
    return client


@frappe.whitelist(methods=["GET"])
def list_routing_preferences():
    """This member's routing rules and their workspace's.

    Returns the empty shape rather than erroring when the site is not
    registered with FAC Cloud yet — a settings page that cannot load is worse
    than one that says there is nothing to show.
    """
    from frappe_assistant_core.chat.fac_cloud_client import get_fac_cloud_client

    client = get_fac_cloud_client()
    if not client:
        return {"mine": [], "team": [], "mode": "off", "can_manage_team": False}

    result = client.list_routing_preferences(user_id=_ar_user_id(frappe.session.user))
    return result or {"mine": [], "team": [], "mode": "off", "can_manage_team": False}


@frappe.whitelist(methods=["POST"])
def create_routing_preference(
    match_kind: str = None,
    match_value: str = None,
    target_tier: str = None,
    scope: str = "Tenant",
    priority: int = None,
):
    """Create a workspace routing rule.

    `scope` accepts only "Tenant" today. A personal rule is the one a member
    would want from the transparency panel, and Sec 11 gates that door on
    Increment B telemetry that does not exist yet — so offering it here would
    let a member create a rule for the whole workspace from their own turn,
    which is not what the action means.
    """
    if scope not in _SCOPES:
        frappe.throw(_("Personal rules aren't available yet."))
    if match_kind not in _MATCH_KINDS:
        frappe.throw(_("Choose what the rule matches on."), frappe.ValidationError)
    if not (match_value or "").strip():
        frappe.throw(_("A rule needs something to match on."), frappe.ValidationError)
    if not target_tier:
        frappe.throw(_("Choose which grade the rule should use."), frappe.ValidationError)

    return _client().create_routing_preference(
        user_id=_ar_user_id(frappe.session.user),
        scope=scope,
        match_kind=match_kind,
        match_value=match_value.strip(),
        target_tier=target_tier,
        priority=priority,
        origin="settings",
    )


@frappe.whitelist(methods=["POST"])
def set_routing_preference_status(preference_id: str = None, status: str = None):
    """Suspend or re-enable a rule."""
    if not preference_id:
        frappe.throw(_("Which rule?"), frappe.ValidationError)
    if status not in _STATUSES:
        frappe.throw(_("Unknown status."), frappe.ValidationError)

    return _client().set_routing_preference_status(
        user_id=_ar_user_id(frappe.session.user),
        preference_id=preference_id,
        status=status,
    )


@frappe.whitelist(methods=["POST"])
def set_routing_preference_mode(preference_id: str = None, rule_mode: str = None):
    """Take a rule live, or send it back to its trial.

    AR enforces that only an admin-capable member may do this to a workspace
    rule; this hop establishes which member is asking.
    """
    if not preference_id:
        frappe.throw(_("Which rule?"), frappe.ValidationError)
    if rule_mode not in _RULE_MODES:
        frappe.throw(_("Unknown rule mode."), frappe.ValidationError)

    return _client().set_routing_preference_mode(
        user_id=_ar_user_id(frappe.session.user),
        preference_id=preference_id,
        rule_mode=rule_mode,
    )


@frappe.whitelist(methods=["POST"])
def delete_routing_preference(preference_id: str = None):
    """Remove a rule outright."""
    if not preference_id:
        frappe.throw(_("Which rule?"), frappe.ValidationError)

    return _client().delete_routing_preference(
        user_id=_ar_user_id(frappe.session.user),
        preference_id=preference_id,
    )


@frappe.whitelist(methods=["POST"])
def forecast_routing_preference(match_kind: str = None, match_value: str = None, target_tier: str = None):
    """What a rule would cost, before the admin saves it."""
    if match_kind not in _MATCH_KINDS or not target_tier:
        frappe.throw(_("Choose a rule type and a grade first."), frappe.ValidationError)

    return _client().forecast_routing_preference(
        user_id=_ar_user_id(frappe.session.user),
        match_kind=match_kind,
        match_value=(match_value or "").strip(),
        target_tier=target_tier,
    )
