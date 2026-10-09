# Frappe Assistant Core - Marketplace API Wrapper
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Marketplace endpoints — wraps assistant_runtime_marketplace via AR SDK.

These endpoints sit alongside (and will eventually replace) the workflow
template marketplace endpoints in api/workflows.py. They route through
``client.marketplace_api_base`` to the new generic listings table.
"""

import json
from typing import NoReturn

import frappe
from frappe import _

from frappe_assistant_core.chat.workflows.template_variables import (
    parse_schema,
    parse_variables,
    validate_template_variables,
)

from ._helpers import ARAPIError, _log, _marketplace_enabled, _redact_upstream_internals, _strip_noise
from .auth import _ar_user_id


def _get_client():
    from frappe_assistant_core.chat.fac_cloud_client import get_fac_cloud_client

    client = get_fac_cloud_client()
    if not client:
        frappe.throw(_("Not connected to FAC Cloud"))
    return client


# Types cloned into the caller's own library; every other type, known or not, needs an admin.
_MEMBER_IMPORTABLE_TYPES = frozenset({"Prompt", "Skill"})


def _require_admin() -> None:
    """Same gate as create_workflow: these calls create or change tenant workflows and listings."""
    if "System Manager" not in frappe.get_roles():
        frappe.throw(_("Only System Managers can manage marketplace workflows."), frappe.PermissionError)


def _marketplace_failure(context: str, e: Exception) -> NoReturn:
    """Log the full error to the Error Log; show the user only what FAC Cloud wrote for them.

    A 4xx whose body FAC Cloud returned as JSON carries a message authored for
    the user ("Listing not found", a plan-tier refusal). Anything else (a 5xx,
    a timeout, a non-JSON 4xx whose text embeds the request URL, a bug here)
    is replaced with a generic sentence.
    Call from inside an ``except`` block so the traceback is logged too.
    """
    _log("FACO Marketplace", f"{context}: {e!s}")
    status = getattr(e, "status_code", None)
    if isinstance(e, ARAPIError) and status and 400 <= status < 500 and e.response_data:
        message = _redact_upstream_internals(_strip_noise(getattr(e, "message", "") or ""))
        # With no message key in the body, the SDK falls back to str(HTTPError), which
        # embeds the request URL and tenant id.
        if message and "://" not in message and "for url:" not in message:
            frappe.throw(message)
    frappe.throw(_("The marketplace could not complete this request. Please try again in a moment."))


# ---------------------------------------------------------------------------
# Browse / inspect
# ---------------------------------------------------------------------------


@frappe.whitelist(methods=["GET"])
def list_listings(
    listing_type: str | None = None,
    category: str | None = None,
    search: str | None = None,
    featured_only: str | None = None,
    min_rating: str | None = None,
    plan_tier: str | None = None,
    sort_by: str | None = None,
    page: int = 0,
    page_size: int = 20,
):
    """List marketplace listings (workflows / prompts / skills) for this tenant."""
    from frappe_assistant_core.chat.fac_cloud_client import get_fac_cloud_client

    if not _marketplace_enabled() or not (client := get_fac_cloud_client()):
        return {
            "listings": [],
            "total": 0,
            "page": 0,
            "page_size": int(page_size),
            "marketplace_enabled": False,
        }
    try:
        return client.list_listings(
            listing_type=listing_type,
            category=category,
            search=search,
            featured_only=bool(int(featured_only or 0)),
            min_rating=float(min_rating) if min_rating else None,
            plan_tier=plan_tier,
            sort_by=sort_by,
            page=int(page),
            page_size=int(page_size),
            user_id=_ar_user_id(frappe.session.user),
        )
    except Exception as e:
        _log("FACO Marketplace", f"Error listing listings: {e!s}")
        return {
            "listings": [],
            "total": 0,
            "page": 0,
            "page_size": 20,
            "marketplace_enabled": False,
            "error": _("Could not reach FAC Cloud to list templates. Try again in a moment."),
        }


@frappe.whitelist(methods=["GET"])
def get_listing(name: str, include_source: str | None = "1"):
    """Get full listing details + the wrapped source record."""
    if not name:
        frappe.throw(_("name is required"), frappe.ValidationError)

    try:
        client = _get_client()
        return client.get_listing(
            name=name,
            user_id=_ar_user_id(frappe.session.user),
            include_source=bool(int(include_source or 0)),
        )
    except (frappe.ValidationError, frappe.PermissionError):
        raise
    except Exception as e:
        _marketplace_failure("Error getting listing", e)


# ---------------------------------------------------------------------------
# Import
# ---------------------------------------------------------------------------


@frappe.whitelist(methods=["POST"])
def import_listing(
    name: str,
    new_title: str | None = None,
    variables: str | dict | None = None,
    default_model_id: str | None = None,
):
    """Import a marketplace listing into this tenant.

    A Workflow listing becomes a Draft AR Workflow, so it needs the same
    System Manager role as create_workflow. Prompts and skills are cloned into
    the caller's own library and stay open to every user. A workflow's variables
    are checked here against the template's typed schema, because only this
    site can tell whether a Link value exists.
    """
    if not name:
        frappe.throw(_("name is required"), frappe.ValidationError)

    try:
        client = _get_client()
        user_id = _ar_user_id(frappe.session.user)
        listing = client.get_listing(name=name, user_id=user_id, include_source=True)
        listing_type = listing.get("listing_type") if isinstance(listing, dict) else None
        if listing_type not in _MEMBER_IMPORTABLE_TYPES:
            _require_admin()
        return client.import_listing(
            user_id=user_id,
            name=name,
            new_title=new_title,
            variables=_import_variables(_checked_variables(listing, variables)),
            default_model_id=default_model_id,
        )
    except (frappe.ValidationError, frappe.PermissionError):
        raise
    except Exception as e:
        _marketplace_failure("Error importing listing", e)


def _checked_variables(listing: dict, variables: str | dict | None) -> str | dict | None:
    """Validate a workflow's variables against its schema; other listings pass through."""
    if listing.get("listing_type") != "Workflow":
        return variables
    source = listing.get("source")
    if not isinstance(source, dict):
        frappe.throw(
            _("Could not read this template's settings from FAC Cloud. Please try again."),
            frappe.ValidationError,
        )
    values = validate_template_variables(
        parse_schema(source.get("variables_schema")), parse_variables(variables)
    )
    return values or None


def _import_variables(variables: str | dict | None) -> str | None:
    """Serialise import variables for FAC Cloud."""
    if not variables:
        return None
    return json.dumps(variables) if isinstance(variables, dict) else variables


# ---------------------------------------------------------------------------
# Manage own listings
# ---------------------------------------------------------------------------


@frappe.whitelist(methods=["POST"])
def update_listing(
    name: str,
    title: str | None = None,
    short_description: str | None = None,
    description: str | None = None,
    category: str | None = None,
    tags: str | None = None,
    icon: str | None = None,
    is_public: str | None = None,
    is_published: str | None = None,
    plan_tier: str | None = None,
):
    """Update a marketplace listing's metadata."""
    _require_admin()
    if not name:
        frappe.throw(_("name is required"), frappe.ValidationError)

    def _to_bool(v):
        if v is None:
            return None
        return str(v).lower() not in ("0", "false", "")

    try:
        client = _get_client()
        return client.update_listing(
            name=name,
            title=title,
            short_description=short_description,
            description=description,
            category=category,
            tags=tags,
            icon=icon,
            is_public=_to_bool(is_public),
            is_published=_to_bool(is_published),
            plan_tier=plan_tier,
        )
    except (frappe.ValidationError, frappe.PermissionError):
        raise
    except Exception as e:
        _marketplace_failure("Error updating listing", e)


@frappe.whitelist(methods=["POST"])
def delete_listing(name: str):
    """Delete a marketplace listing."""
    _require_admin()
    if not name:
        frappe.throw(_("name is required"), frappe.ValidationError)

    try:
        client = _get_client()
        return client.delete_listing(name=name)
    except (frappe.ValidationError, frappe.PermissionError):
        raise
    except Exception as e:
        _marketplace_failure("Error deleting listing", e)


# ---------------------------------------------------------------------------
# Engagement
# ---------------------------------------------------------------------------


@frappe.whitelist(methods=["POST"])
def rate_listing(listing: str, rating: int, review: str | None = None):
    """Submit (or update) a 1-5 star rating + optional review."""
    if not listing:
        frappe.throw(_("listing is required"), frappe.ValidationError)
    rating = int(rating)
    if rating < 1 or rating > 5:
        frappe.throw(_("rating must be between 1 and 5"))

    try:
        client = _get_client()
        return client.rate_listing(
            user_id=_ar_user_id(frappe.session.user),
            listing=listing,
            rating=rating,
            review=review,
        )
    except (frappe.ValidationError, frappe.PermissionError):
        raise
    except Exception as e:
        _marketplace_failure("Error rating listing", e)


@frappe.whitelist(methods=["POST"])
def report_listing(listing: str, reason: str, details: str | None = None):
    """File an abuse / spam / copyright report against a listing."""
    if not listing or not reason:
        frappe.throw(_("listing and reason are required"), frappe.ValidationError)

    try:
        client = _get_client()
        return client.report_listing(
            user_id=_ar_user_id(frappe.session.user),
            listing=listing,
            reason=reason,
            details=details,
        )
    except (frappe.ValidationError, frappe.PermissionError):
        raise
    except Exception as e:
        _marketplace_failure("Error reporting listing", e)


# ---------------------------------------------------------------------------
# Moderation (admin)
# ---------------------------------------------------------------------------


@frappe.whitelist(methods=["GET"])
def list_pending_reviews(page: int = 0, page_size: int = 20):
    """Admin: list listings awaiting moderation."""
    if "System Manager" not in frappe.get_roles():
        frappe.throw(_("Admin role required"), frappe.PermissionError)
    if not _marketplace_enabled():
        return {"listings": [], "total": 0, "page": int(page), "page_size": int(page_size)}
    try:
        client = _get_client()
        return client.list_pending_reviews(page=int(page), page_size=int(page_size))
    except Exception as e:
        frappe.log_error(title="FACO Marketplace", message=f"Error listing pending reviews: {e!s}")
        return {"listings": [], "total": 0, "page": 0, "page_size": 20}


@frappe.whitelist(methods=["POST"])
def approve_listing(listing: str, notes: str | None = None):
    """Admin: approve a listing for cross-tenant visibility."""
    if "System Manager" not in frappe.get_roles():
        frappe.throw(_("Admin role required"), frappe.PermissionError)
    try:
        client = _get_client()
        return client.approve_listing(listing=listing, notes=notes)
    except (frappe.ValidationError, frappe.PermissionError):
        raise
    except Exception as e:
        _marketplace_failure("Error approving listing", e)


@frappe.whitelist(methods=["POST"])
def reject_listing(listing: str, notes: str | None = None):
    """Admin: reject a listing's moderation request."""
    if "System Manager" not in frappe.get_roles():
        frappe.throw(_("Admin role required"), frappe.PermissionError)
    try:
        client = _get_client()
        return client.reject_listing(listing=listing, notes=notes)
    except (frappe.ValidationError, frappe.PermissionError):
        raise
    except Exception as e:
        _marketplace_failure("Error rejecting listing", e)


# ---------------------------------------------------------------------------
# Creator
# ---------------------------------------------------------------------------


@frappe.whitelist(methods=["GET"])
def get_creator_stats():
    """Aggregate stats for listings authored by this tenant."""
    _empty = {
        "templates_published": 0,
        "total_imports": 0,
        "total_ratings": 0,
        "weighted_average_rating": 0,
        "total_credits_earned": 0,
        "by_type": {},
    }
    if not _marketplace_enabled():
        return _empty
    try:
        client = _get_client()
        return client.get_creator_stats(user_id=_ar_user_id(frappe.session.user))
    except Exception as e:
        frappe.log_error(title="FACO Marketplace", message=f"Error fetching creator stats: {e!s}")
        return _empty


@frappe.whitelist(methods=["GET"])
def list_my_listings(
    listing_type: str | None = None,
    page: int = 0,
    page_size: int = 20,
):
    """List listings created by this tenant."""
    if not _marketplace_enabled():
        return {"listings": [], "total": 0, "page": int(page), "page_size": int(page_size)}
    try:
        client = _get_client()
        return client.list_my_listings(
            user_id=_ar_user_id(frappe.session.user),
            listing_type=listing_type,
            page=int(page),
            page_size=int(page_size),
        )
    except Exception as e:
        frappe.log_error(title="FACO Marketplace", message=f"Error listing my listings: {e!s}")
        return {"listings": [], "total": 0, "page": 0, "page_size": 20}


# ---------------------------------------------------------------------------
# Publishing / downloads / version checks (chunk 5)
# ---------------------------------------------------------------------------


@frappe.whitelist(methods=["POST"])
def publish_workflow(
    workflow_name: str,
    template_name: str | None = None,
    category: str = "General",
    short_description: str | None = None,
    description: str | None = None,
    tags: str | None = None,
    is_public: str | None = None,
    plan_tier: str | None = None,
):
    """Export a tenant-owned workflow + publish it as a marketplace listing."""
    if "System Manager" not in frappe.get_roles():
        frappe.throw(_("Only administrators can publish workflows"), frappe.PermissionError)
    if not workflow_name:
        frappe.throw(_("workflow_name is required"), frappe.ValidationError)
    try:
        client = _get_client()
        return client.publish_workflow(
            user_id=_ar_user_id(frappe.session.user),
            workflow_name=workflow_name,
            template_name=template_name,
            category=category,
            short_description=short_description,
            description=description,
            tags=tags,
            is_public=str(is_public).lower() in ("1", "true") if is_public is not None else False,
            plan_tier=plan_tier,
        )
    except (frappe.ValidationError, frappe.PermissionError):
        raise
    except Exception as e:
        _marketplace_failure("Error publishing workflow", e)


@frappe.whitelist(methods=["GET"])
def download_listing_as_json(name: str):
    """Return a workflow listing as portable ar_workflow_template_v1 JSON."""
    if not name:
        frappe.throw(_("name is required"), frappe.ValidationError)
    try:
        client = _get_client()
        return client.download_listing_as_json(name=name)
    except (frappe.ValidationError, frappe.PermissionError):
        raise
    except Exception as e:
        _marketplace_failure("Error downloading listing", e)


@frappe.whitelist(methods=["GET"])
def check_workflow_update(name: str):
    """Check whether the workflow's source template has a newer version."""
    if not name:
        frappe.throw(_("name is required"), frappe.ValidationError)
    try:
        client = _get_client()
        return client.check_workflow_update(name=name)
    except frappe.ValidationError:
        raise
    except Exception as e:
        frappe.log_error(title="FACO Marketplace", message=f"Error checking workflow update: {e!s}")
        return {"has_update": False, "reason": "error"}


@frappe.whitelist(methods=["GET"])
def check_all_workflow_updates():
    """Batch-check all tenant workflows for available template updates."""
    if not _marketplace_enabled():
        return {"updates": []}
    try:
        client = _get_client()
        return client.check_all_workflow_updates()
    except Exception as e:
        frappe.log_error(title="FACO Marketplace", message=f"Error checking workflow updates: {e!s}")
        return {"updates": []}
