import frappe

from frappe_assistant_core.chat.gate import is_chat_enabled
from frappe_assistant_core.chat.utils.security_headers import apply_spa_headers

no_cache = 1


def get_context(context):
    """
    Context provider for the Frappe Assistant Copilot Vue.js frontend
    """
    # Runtime gate: when FAC Chat is disabled the SPA route returns 404.
    # The route itself is registered unconditionally so toggling chat on
    # makes it live immediately without a worker restart.
    if not is_chat_enabled():
        raise frappe.PageDoesNotExistError

    # Security: CSP, X-Frame-Options, Referrer-Policy for the SPA shell.
    # Applied to all /copilot/* routes since conversations.py and
    # settings.py re-export this get_context unchanged.
    apply_spa_headers()

    # Require authentication. Keep the original path and query, so a
    # verification link opened while logged out still completes after login.
    if frappe.session.user == "Guest":
        import urllib.parse

        target = frappe.request.path if frappe.request else "/copilot"
        query = frappe.request.query_string if frappe.request else b""
        if query:
            target = f"{target}?{query.decode()}"
        frappe.local.flags.redirect_location = "/login?redirect-to=" + urllib.parse.quote(target)
        raise frappe.Redirect

    csrf_token = frappe.sessions.get_csrf_token()
    # CSRF token is generated lazily and must be persisted before the page
    # renders, otherwise subsequent POSTs from the SPA fail validation.
    frappe.db.commit()  # nosemgrep: frappe-manual-commit

    context = frappe._dict()
    context.csrf_token = csrf_token
    context.boot = get_boot()
    return context


@frappe.whitelist(methods=["POST"])
def get_context_for_dev():
    """Development mode context for hot reload.

    FACO-M4: previously allowed ``allow_guest=True`` behind a
    ``developer_mode`` gate. Misconfigured staging/prod often leaves
    ``developer_mode=1`` on, which would expose ``get_boot()`` (csrf_token,
    socketio port, session user) to unauthenticated callers. The boot
    payload is already only useful for logged-in users during Vite HMR, so
    requiring session auth closes the hole without affecting the intended
    workflow.
    """
    if not frappe.conf.developer_mode:
        frappe.throw(frappe._("This method is only meant for developer mode"))
    return get_boot()


def get_boot():
    """
    Get boot data for the frontend
    """
    # Get user's theme preference (Dark / Light / Automatic)
    user_theme = frappe.db.get_value("User", frappe.session.user, "desk_theme") or "Light"
    theme_map = {"Dark": "dark", "Light": "light", "Automatic": "automatic"}
    theme = theme_map.get(user_theme, "light")

    bootinfo = {
        "site_name": str(frappe.local.site),
        "user": str(frappe.session.user),
        "csrf_token": str(frappe.sessions.get_csrf_token()),
        "lang": str(frappe.local.lang or "en"),
        "theme": theme,
        "socketio_port": frappe.conf.get("socketio_port") or 9000,
    }

    # Get user's full name for display
    user_info = (
        frappe.db.get_value("User", frappe.session.user, ["full_name", "user_image"], as_dict=True) or {}
    )
    bootinfo["user_fullname"] = user_info.get("full_name") or frappe.session.user
    bootinfo["user_image"] = user_info.get("user_image") or ""

    # FACO SPA has no translation files and doesn't use __translations
    bootinfo["__translations"] = {}

    return bootinfo
