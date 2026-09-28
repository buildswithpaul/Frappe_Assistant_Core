# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Mobile API — bearer-authenticated helpers for the FAC mobile app.

The Socket.IO session lookup, the WebView session bridge and private-file
download. Chat itself goes through the same endpoints as the SPA.
"""

import frappe
from frappe import _
from werkzeug import Response


def _assert_mobile_oauth_request() -> None:
    """FACO-M5: refuse ``create_web_session`` unless the caller authenticated
    via an OAuth Bearer Token issued to a FACO Mobile OAuth client.

    The bridge plants browser cookies from a bearer token — any client not
    issued via the mobile dynamic-registration flow (``api.auth:755``) has no
    business minting browser sessions. API keys, session cookies, and the AR
    integration client are refused.
    """
    header = frappe.get_request_header("Authorization", "") or ""
    if not header.lower().startswith("bearer "):
        frappe.throw(
            _("create_web_session requires OAuth Bearer authentication"),
            frappe.AuthenticationError,
        )
    access_token = header.split(None, 1)[1].strip()
    if not access_token:
        frappe.throw(_("Missing bearer token"), frappe.AuthenticationError)

    client_name = frappe.db.get_value(
        "OAuth Bearer Token",
        {"access_token": access_token, "status": "Active"},
        "client",
    )
    if not client_name:
        frappe.throw(_("Invalid bearer token"), frappe.AuthenticationError)

    # FACO Mobile clients are registered with ``app_name = "FACO Mobile"``
    # by ``api.auth:791``. The FAC Cloud integration client uses
    # ``app_name = "FAC Cloud"``, which is correctly rejected.
    app_name = frappe.db.get_value("OAuth Client", client_name, "app_name")
    if app_name != "FACO Mobile":
        frappe.throw(
            _("This OAuth client is not allowed to use create_web_session"),
            frappe.PermissionError,
        )


@frappe.whitelist(methods=["GET"])
def create_web_session() -> Response:
    """Create a browser session from a Bearer token and redirect.

    Uses GET: the mobile WebView reaches this via a top-level page navigation,
    which can only issue GET. CSRF is a non-concern — the caller is authenticated
    solely by the OAuth Bearer header (cross-checked to a FACO Mobile client in
    ``_assert_mobile_oauth_request``); no ambient cookie is trusted on the way in.

    Mobile WebView calls this URL with Authorization header. The response
    uses Frappe's LoginManager to create a full session, then returns an
    HTML page that sets all session cookies via document.cookie and redirects
    to the target page. This avoids iOS WebView issues where Set-Cookie
    headers on 3xx responses are not persisted.

    Query params:
            redirect_to (str): The Frappe page to open after auth (e.g. /app/sales-order/SO-001)
    """
    import json as _json

    redirect_to = frappe.form_dict.get("redirect_to") or "/app"
    user = frappe.session.user

    if user == "Guest":
        frappe.throw(_("Authentication required"), frappe.AuthenticationError)

    # FACO-M5: the bearer-to-cookie bridge is meant for the mobile WebView,
    # not generic API tokens. Require the request to have been authenticated
    # via an OAuth Bearer Token (not API key / session cookie) and cross-check
    # the token's client against the allow-list of known mobile OAuth clients.
    _assert_mobile_oauth_request()

    # SECURITY: Only allow same-site absolute paths. Reject scheme URIs
    # (javascript:, data:, http://evil.example/...) and protocol-relative URLs
    # (//evil.example). This runs before the value is inlined into a <script>.
    if not redirect_to.startswith("/") or redirect_to.startswith("//"):
        redirect_to = "/app"

    # Use Frappe's official LoginManager — runs hooks, creates session, sets all cookies
    login_manager = frappe.auth.LoginManager()
    login_manager.login_as(user)

    # Build JS cookie-setting code from all cookies LoginManager prepared
    cookie_lines = []
    for key, opts in frappe.local.cookie_manager.cookies.items():
        value = opts.get("value") or ""
        max_age = opts.get("max_age") or ""
        # FACO-M5: SameSite=Strict neutralizes cross-site request forgery if
        # the planted cookie ever leaks to a third-party context. The mobile
        # WebView navigates same-origin after this bridge, so Strict is safe.
        cookie_lines.append(
            f'document.cookie = "{key}={value}; path=/; SameSite=Strict; Secure'
            + (f"; max-age={max_age}" if max_age else "")
            + '";'
        )

    cookies_js = "\n".join(cookie_lines)

    # JSON-encode for JS string context. html.escape would be wrong here —
    # it doesn't neutralize javascript:/data: URIs and breaks inside quoted
    # JS literals. json.dumps emits a correctly-escaped JS string literal.
    safe_redirect_js = _json.dumps(redirect_to)

    # Return HTML that sets cookies on the real origin, then redirects
    page = f"""<!DOCTYPE html>
<html><head><script>
{cookies_js}
window.location.replace({safe_redirect_js});
</script></head><body></body></html>"""

    return Response(page, status=200, content_type="text/html")


@frappe.whitelist(methods=["GET"])
def download_file_by_token(file_url: str | None = None) -> Response:
    """Serve private file content authenticated via Bearer token.

    Mobile clients can't use cookie-based file access due to iOS CSRF issues
    (SFSafariViewController sets cookies in the shared jar, triggering CSRF checks).
    This endpoint validates Bearer token auth and returns the raw file content.

    Args:
            file_url (str): The private file URL, e.g. /private/files/document.pdf
    """
    if frappe.session.user == "Guest":
        frappe.throw(_("Authentication required"), frappe.AuthenticationError)

    if not file_url:
        frappe.throw(_("file_url is required"))

    import mimetypes
    import os

    # Look up the File doc via its file_url — do NOT derive a disk path from
    # user input. Then delegate the authorization decision to the File doctype,
    # which respects is_private + the attached_to_doctype ownership chain.
    file_doc_name = frappe.db.get_value("File", {"file_url": file_url}, "name")
    if not file_doc_name:
        frappe.throw(_("File not found"), frappe.DoesNotExistError)

    file_doc = frappe.get_doc("File", file_doc_name)
    file_doc.check_permission(ptype="read")

    # Only after the permission check, resolve the real on-disk path.
    file_path = file_doc.get_full_path()

    if not os.path.exists(file_path):
        frappe.throw(_("File not found"), frappe.DoesNotExistError)

    # file_path comes from a permission-checked File doc (check_permission at
    # line 151) — the caller's file_url is never used to build the path.
    with open(file_path, "rb") as f:  # nosemgrep: frappe-security-file-traversal
        content = f.read()

    filename = os.path.basename(file_path)
    content_type = mimetypes.guess_type(file_url)[0] or "application/octet-stream"

    return Response(
        content,
        status=200,
        content_type=content_type,
        headers={
            "Content-Disposition": f'inline; filename="{filename}"',
        },
    )


@frappe.whitelist(methods=["GET"])
def get_socket_session() -> dict:
    """Return the current session ID so mobile clients can authenticate Socket.IO.

    Frappe's socket server uses the `sid` cookie to identify users. Mobile apps
    can't share cookies between fetch() and socket.io-client, so this endpoint
    returns the sid value explicitly.
    """
    return {
        "sid": frappe.session.sid,
        "user": frappe.session.user,
        "site_name": frappe.local.site,
    }
