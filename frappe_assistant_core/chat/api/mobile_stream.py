# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Mobile API — bearer-authenticated helpers for the FAC mobile app.

The Socket.IO session lookup, the WebView session bridge and private-file
download. Chat itself goes through the same endpoints as the SPA.
"""

import json
import unicodedata
from urllib.parse import quote

import frappe
from frappe import _
from werkzeug import Response

from ._mobile_sessions import mobile_client_of_request, record_web_session

DEFAULT_REDIRECT = "/app"


def _script_string(value: str) -> str:
    """``value`` as a JS string literal that is safe inside an inline ``<script>``.

    ``json.dumps`` escapes quotes, backslashes and control characters but not
    ``<``, ``>`` or ``&``, and the HTML tokenizer ends a script element at the
    first ``</script>`` whatever the JS string context. Their ``\\u`` escapes
    keep the JS value identical.
    """
    return json.dumps(value).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def _same_site_path(value: object) -> str:
    """``value`` when it is a same-site absolute path, otherwise ``/app``.

    Refuses scheme URIs (``javascript:``, ``https://evil.example``) and
    protocol-relative ``//evil.example``. Also refuses a backslash and any
    whitespace or control character (spec §8.3): browsers read a backslash as
    a slash and drop tabs and newlines, so ``/`` + backslash + ``evil.example``
    and ``/`` + tab + ``/evil.example`` both open ``//evil.example``.
    """
    if not isinstance(value, str) or not value.startswith("/") or value.startswith("//"):
        return DEFAULT_REDIRECT
    if any(ch == "\\" or ch.isspace() or unicodedata.category(ch) == "Cc" for ch in value):
        return DEFAULT_REDIRECT
    return value


@frappe.whitelist(methods=["GET"])
def create_web_session() -> Response:
    """Create a browser session from a Bearer token and redirect.

    Uses GET: the mobile WebView reaches this via a top-level page navigation,
    which can only issue GET. CSRF is a non-concern — the caller is authenticated
    solely by the OAuth Bearer header (cross-checked to a FAC mobile client in
    ``mobile_client_of_request``); no ambient cookie is trusted on the way in.

    Mobile WebView calls this URL with Authorization header. The response
    uses Frappe's LoginManager to create a full session, then returns an
    HTML page that sets all session cookies via document.cookie and redirects
    to the target page. This avoids iOS WebView issues where Set-Cookie
    headers on 3xx responses are not persisted.

    Query params:
            redirect_to (str): The Frappe page to open after auth (e.g. /app/sales-order/SO-001)
    """
    redirect_to = frappe.form_dict.get("redirect_to")
    user = frappe.session.user

    if user == "Guest":
        frappe.throw(_("Authentication required"), frappe.AuthenticationError)

    # FACO-M5: the bearer-to-cookie bridge is meant for the mobile WebView,
    # not generic API tokens. Require the request to have been authenticated
    # via an OAuth Bearer Token (not API key / session cookie) and cross-check
    # the token's client against the allow-list of known mobile OAuth clients.
    client = mobile_client_of_request()

    # SECURITY: only a same-site absolute path survives (_same_site_path); the
    # page inlines it through _script_string, which stops it ending the <script>.
    redirect_to = _same_site_path(redirect_to)

    # Use Frappe's official LoginManager — runs hooks, creates session, sets all cookies
    login_manager = frappe.auth.LoginManager()
    login_manager.login_as(user)
    # Sign-out ends exactly the sessions this device minted (auth.revoke_mobile_session).
    record_web_session(user, frappe.session.sid, client)

    # Build JS cookie-setting code from all cookies LoginManager prepared.
    # Values are percent-encoded exactly as CookieManager.flush_cookies encodes
    # a Set-Cookie value (the desk decodes them), so a user-editable value such
    # as full_name or user_image can carry no quote, semicolon or markup.
    cookie_lines = []
    for key, opts in frappe.local.cookie_manager.cookies.items():
        value = quote((opts.get("value") or "").encode("utf-8"))
        max_age = opts.get("max_age") or ""
        # FACO-M5: SameSite=Strict neutralizes cross-site request forgery if
        # the planted cookie ever leaks to a third-party context. The mobile
        # WebView navigates same-origin after this bridge, so Strict is safe.
        cookie = f"{key}={value}; path=/; SameSite=Strict; Secure"
        if max_age:
            cookie += f"; max-age={max_age}"
        cookie_lines.append(f"document.cookie = {_script_string(cookie)};")

    cookies_js = "\n".join(cookie_lines)

    # Return HTML that sets cookies on the real origin, then redirects
    page = f"""<!DOCTYPE html>
<html><head><script>
{cookies_js}
window.location.replace({_script_string(redirect_to)});
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
