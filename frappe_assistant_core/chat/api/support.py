# FACO - Support (Tickets & Feedback) API
# Copyright (C) 2025 Paul Clinton
#
# Proprietary License

"""Proxy endpoints for raising support tickets and product feedback.

Bridges the FAC user session to HMAC-signed AR calls via the SDK, mirroring
chat/api/privacy.py. Tickets return a tokenized Helpdesk portal link; feedback
is fire-and-forget.
"""

import base64
import binascii
import json
import platform
import shutil
import subprocess  # nosec

import frappe
from frappe import _
from frappe.utils import cint
from frappe.utils.caching import redis_cache

from frappe_assistant_core.chat.fac_cloud_client import get_fac_cloud_client

from ._attachment_validation import is_ticket_image, validate_ticket_attachment
from ._rate_limits import rate_limit, session_user_or_ip


def _get_client():
    client = get_fac_cloud_client()
    if not client:
        frappe.throw(_("Support is not available right now."))
    return client


MAX_TRANSCRIPT_BYTES = 200 * 1024
MAX_TRANSCRIPT_MESSAGES = 200
_TRUNCATION_NOTE = "\n\n---\n_Earlier turns omitted — transcript truncated._\n"

_ROLE_LABELS = {"user": "User", "assistant": "Assistant", "system": "System"}


def _render_transcript(session_id: str | None) -> str | None:
    """Render the caller's own chat session as Markdown, or None if empty.

    Only runs when the user ticked "Include this conversation". Scoped to
    frappe.session.user because frappe.get_all bypasses permissions — this
    filter is the only thing stopping a crafted session_id reading someone
    else's chat.
    """
    if not session_id:
        return None

    rows = frappe.get_all(
        "FAC Chat Message",
        filters={"session_id": session_id, "user": frappe.session.user},
        fields=["role", "content", "model", "timestamp"],
        order_by="timestamp asc, creation asc",
        limit=MAX_TRANSCRIPT_MESSAGES,
    )
    if not rows:
        return None

    parts = [f"# Conversation transcript\n\nSession: {session_id}\n"]
    for row in rows:
        role = _ROLE_LABELS.get((row.get("role") or "").lower(), row.get("role") or "Unknown")
        heading = f"## {role}"
        if row.get("model"):
            heading += f" · {row['model']}"
        if row.get("timestamp"):
            heading += f" · {row['timestamp']}"
        parts.append(f"{heading}\n\n{row.get('content') or ''}\n")

    return _clip("\n".join(parts))


def _clip(text: str) -> str:
    """Bound the transcript so a long session can't bloat the ticket."""
    encoded = text.encode("utf-8")
    if len(encoded) <= MAX_TRANSCRIPT_BYTES:
        return text
    budget = MAX_TRANSCRIPT_BYTES - len(_TRUNCATION_NOTE.encode("utf-8"))
    return encoded[:budget].decode("utf-8", errors="ignore") + _TRUNCATION_NOTE


def _coerce_env(environment: dict | str | None) -> dict | None:
    """Accept a dict or a JSON string from form data; return a dict or None."""
    if environment in (None, ""):
        return None
    if isinstance(environment, str):
        try:
            return json.loads(environment)
        except (ValueError, TypeError):
            return {"raw": environment}
    return environment


def _coerce_ids(attachment_ids: list | str | None) -> list | None:
    """Accept a list or a JSON-string list from form data; return list or None.

    Unlike _coerce_env, malformed input drops to None rather than being
    preserved: an id that fails to parse can't reference a real File, so
    forwarding it would just be garbage. Dropping it is the safe choice.
    """
    if attachment_ids in (None, ""):
        return None
    if isinstance(attachment_ids, str):
        try:
            parsed = json.loads(attachment_ids)
        except (ValueError, TypeError):
            return None
        return parsed or None
    return attachment_ids or None


@frappe.whitelist(methods=["GET"])
def get_environment() -> dict:
    """Server-side environment metadata attached to support reports.

    Fetched when the Help & Feedback modal opens; the browser adds its own
    half (user agent, platform, language) before submitting. Ordered so the
    versions support asks for first read first, with the full app inventory
    last.
    """
    apps = _installed_app_versions()

    return {
        "tenant_id": frappe.db.get_single_value("FAC Chat Settings", "tenant_id") or "unregistered",
        "fac_version": apps.get("frappe_assistant_core", "unknown"),
        "frappe_version": apps.get("frappe", "unknown"),
        "erpnext_version": apps.get("erpnext", "not installed"),
        "python_version": platform.python_version(),
        "bench_version": _bench_version(),
        "installed_apps": ", ".join(f"{app} {version}" for app, version in apps.items()),
    }


def _installed_app_versions() -> dict[str, str]:
    """Return {app: version} for every app installed on this site.

    Deliberately not frappe.utils.change_log.get_versions — that shells out to
    `git rev-parse` once per app to resolve branch names we don't report, which
    turns a dictionary lookup into ~20 subprocesses.
    """
    versions = {}
    for app in sorted(frappe.get_installed_apps()):
        try:
            versions[app] = frappe.get_attr(f"{app}.__version__") or "unknown"
        except Exception:
            versions[app] = "unknown"
    return versions


@redis_cache(ttl=60 * 60 * 24)
def _bench_version() -> str:
    """Return the bench CLI version, or "unknown" if bench isn't reachable.

    Bench usually lives outside the site's virtualenv, so the import path only
    works on installs that pip-installed it alongside Frappe (frappe_docker);
    everywhere else we ask the CLI. Cached for a day — this only moves when
    bench itself is upgraded, which restarts the workers anyway.
    """
    try:
        from importlib.metadata import version

        return version("frappe-bench")
    except Exception:
        pass

    bench_bin = shutil.which("bench")
    if not bench_bin:
        return "unknown"

    try:
        result = subprocess.run(  # nosec — fixed argv, resolved binary, no user input
            [bench_bin, "--version"],
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        )
    except Exception:
        return "unknown"

    return result.stdout.strip() or "unknown"


@frappe.whitelist(methods=["POST"])
def create_ticket(
    subject: str | None = None,
    description: str | None = None,
    category: str | None = None,
    conversation_id: str | None = None,
    environment: dict | str | None = None,
    attachment_ids: list | str | None = None,
) -> dict:
    """Raise a support ticket for the current user.

    Returns {ticket_id, portal_link} from AR.
    """
    if not subject:
        frappe.throw(_("A subject is required"))
    if not description:
        frappe.throw(_("A description is required"))

    user = frappe.session.user
    client = _get_client()
    try:
        return client.create_ticket(
            user_id=user,
            subject=subject,
            description=description,
            category=category,
            conversation_id=conversation_id or None,
            environment=_coerce_env(environment),
            attachment_ids=_coerce_ids(attachment_ids),
            conversation_transcript=_render_transcript(conversation_id or None),
        )
    except Exception as e:
        frappe.log_error(title="Support create_ticket failed", message=str(e))
        frappe.throw(_("Couldn't submit your ticket. Please try again."))


@frappe.whitelist(methods=["GET"])
@rate_limit(session_user_or_ip, limit=120, seconds=60)
def download_ticket_attachment(ticket_id: str | int | None = None, file_url: str | None = None):
    """Stream a ticket attachment that physically lives on AR.

    Ticket files are stored on AR, so the URLs AR writes into ticket content
    ("/private/files/...") point at a host this site is not. The SPA rewrites
    them to this endpoint, which fetches over the signed channel and serves the
    bytes from this origin, where the user already has a session.

    GET so it can back an <img src>. AR re-checks that the caller owns both the
    ticket and the file, so this proxy adds no authority of its own.
    """
    if not ticket_id:
        frappe.throw(_("ticket_id is required"))
    if not file_url:
        frappe.throw(_("file_url is required"))

    client = _get_client()
    try:
        content, content_type, filename = client.download_ticket_attachment(
            user_id=frappe.session.user,
            ticket_id=str(ticket_id),
            file_url=file_url,
        )
    except Exception as e:
        frappe.log_error(title="Support download_ticket_attachment failed", message=str(e))
        frappe.throw(_("Couldn't load that attachment."))

    frappe.local.response.filename = filename or "attachment"
    frappe.local.response.filecontent = content
    frappe.local.response.type = "download"
    frappe.local.response.content_type = content_type or "application/octet-stream"


@frappe.whitelist(methods=["POST"])
@rate_limit(session_user_or_ip, limit=10, seconds=60)
def upload_ticket_attachment(
    file_data: str | None = None,
    file_name: str | None = None,
    content_type: str | None = None,
) -> dict:
    """Pre-upload one ticket attachment (image or PDF) for the current user.

    Dual mode: multipart FormData (web) via request.files['file'], or a base64
    JSON payload (mobile). Validates locally, then forwards the bytes to AR via
    the SDK. Returns {file_id, file_url, file_name, is_image}.
    """
    files = frappe.request.files if frappe.request else None
    if files and "file" in files:
        upload = files["file"]
        content = upload.read()
        raw_name = upload.filename
        raw_mime = upload.mimetype or ""
    elif file_data:
        try:
            content = base64.b64decode(file_data)
        except (binascii.Error, ValueError):
            frappe.throw(_("Invalid file data"), frappe.ValidationError)
        raw_name = file_name or "attachment"
        raw_mime = content_type or ""
    else:
        frappe.throw(_("No file uploaded"), frappe.ValidationError)

    safe_name, canonical_mime = validate_ticket_attachment(content, raw_name, raw_mime)

    client = _get_client()
    try:
        result = client.upload_ticket_attachment(
            user_id=frappe.session.user,
            file_data=content,
            file_name=safe_name,
            content_type=canonical_mime,
        )
    except Exception as e:
        frappe.log_error(title="Support upload_ticket_attachment failed", message=str(e))
        frappe.throw(_("Couldn't upload your attachment. Please try again."))

    if not result or not result.get("file_id"):
        frappe.throw(_("Couldn't upload your attachment. Please try again."))

    return {
        "file_id": result.get("file_id"),
        "file_url": result.get("file_url"),
        "file_name": result.get("file_name", safe_name),
        "is_image": bool(result.get("is_image", is_ticket_image(safe_name, canonical_mime))),
    }


@frappe.whitelist(methods=["POST"])
def submit_feedback(
    rating: int | str | None = None,
    comment: str | None = None,
    category: str | None = None,
    environment: dict | str | None = None,
) -> dict:
    """Submit product/service feedback for the current user.

    Returns {feedback_id} from AR. Deliberately carries no conversation
    reference: the feedback form never asks for one, so sending it would be
    undisclosed collection. Tickets ask, and attach the transcript.
    """
    user = frappe.session.user
    client = _get_client()
    try:
        return client.submit_feedback(
            user_id=user,
            rating=cint(rating) if rating not in (None, "") else None,
            comment=comment or None,
            category=category or None,
            environment=_coerce_env(environment),
        )
    except Exception as e:
        frappe.log_error(title="Support submit_feedback failed", message=str(e))
        frappe.throw(_("Couldn't submit your feedback. Please try again."))


@frappe.whitelist(methods=["POST"])
def list_my_tickets(status: str | None = None) -> list:
    """List the current user's support tickets."""
    user = frappe.session.user
    client = _get_client()
    try:
        return client.list_tickets(user_id=user, status=status or None) or []
    except Exception as e:
        frappe.log_error(title="Support list_my_tickets failed", message=str(e))
        frappe.throw(_("Couldn't load your tickets. Please try again."))


@frappe.whitelist(methods=["POST"])
def list_my_feedback() -> list:
    """List the current user's submitted feedback."""
    user = frappe.session.user
    client = _get_client()
    try:
        return client.list_feedback(user_id=user) or []
    except Exception as e:
        frappe.log_error(title="Support list_my_feedback failed", message=str(e))
        frappe.throw(_("Couldn't load your feedback. Please try again."))


@frappe.whitelist(methods=["POST"])
def get_ticket_thread(ticket_id: str | int | None = None) -> dict:
    """Return one ticket's header + conversation thread for the current user."""
    if not ticket_id:
        frappe.throw(_("ticket_id is required"))

    user = frappe.session.user
    client = _get_client()
    try:
        return client.get_ticket_thread(user_id=user, ticket_id=str(ticket_id))
    except Exception as e:
        frappe.log_error(title="Support get_ticket_thread failed", message=str(e))
        frappe.throw(_("Couldn't load that ticket. Please try again."))


@frappe.whitelist(methods=["POST"])
def reply_to_ticket(
    ticket_id: str | int | None = None,
    message: str | None = None,
    attachment_ids: list | str | None = None,
) -> dict:
    """Post the current user's reply to their ticket."""
    if not ticket_id:
        frappe.throw(_("ticket_id is required"))
    if not message or not message.strip():
        frappe.throw(_("A message is required"))

    user = frappe.session.user
    client = _get_client()
    try:
        return client.reply_to_ticket(
            user_id=user,
            ticket_id=str(ticket_id),
            message=message,
            attachment_ids=_coerce_ids(attachment_ids),
        )
    except Exception as e:
        frappe.log_error(title="Support reply_to_ticket failed", message=str(e))
        frappe.throw(_("Couldn't send your reply. Please try again."))
