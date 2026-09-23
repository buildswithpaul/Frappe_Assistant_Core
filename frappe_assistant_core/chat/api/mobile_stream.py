# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Mobile API — session helper for Socket.IO auth."""

import json

import frappe
from frappe import _
from frappe.query_builder.functions import Count, Max, Min
from werkzeug import Response

from ._helpers import (
    _not_registered_error,
    _safe_error,
)
from ._untrusted import wrap_untrusted
from .auth import _ar_user_id


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


@frappe.whitelist(methods=["POST"])
def stream_chat(
    session_id: str, message: str, model_id: str | None = None, attachments: str | None = None
) -> Response:
    """
    Send a message and stream AI response via Server-Sent Events (SSE).

    This endpoint is designed for mobile clients that can't use Socket.IO.
    It returns a streaming response with SSE events directly.

    Args:
            session_id (str): Conversation session ID
            message (str): User's message
            model_id (str): Optional model ID to use for this request
            attachments (str): JSON array of attachments for Vision API
                    Each: {type: "image", format: "png|jpeg|...", data: "<base64>", name: "..."}

    Returns:
            Generator: SSE event stream
    """
    # Parse attachments if provided as string
    if isinstance(attachments, str):
        attachments = json.loads(attachments) if attachments else []
    if not attachments:
        attachments = []

    # Check if user can use FACO
    from .settings import can_use_faco

    access_check = can_use_faco()
    if not access_check.get("can_use"):
        frappe.throw(_(access_check.get("reason", "Cannot use FACO")))

    # Save user message to database
    from frappe_assistant_core.chat.doctype.fac_chat_message.fac_chat_message import (
        FACChatMessage,
    )

    user_msg = FACChatMessage.create_message(
        session_id=session_id, role="user", content=message, context=None
    )

    # Extract file attachments if any — wrap in untrusted envelope
    # (FACO-H15 prompt injection defense).
    file_content = _extract_file_attachments(user_msg.name)
    system_prompt_addendum = None
    if file_content:
        system_prompt_addendum = wrap_untrusted(file_content, kind="user_attached_files")

    # Return a werkzeug streaming Response directly (bypasses Frappe's response system)
    generator = _stream_generator(
        session_id=session_id,
        message=message,
        user_msg_name=user_msg.name,
        model_id=model_id,
        attachments=attachments,
        system_prompt_addendum=system_prompt_addendum,
    )

    return Response(
        generator,
        content_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def _stream_generator(
    session_id, message, user_msg_name, model_id=None, attachments=None, system_prompt_addendum=None
):
    """
    Generator function that yields SSE events from AR stream.

    This function connects to AR's streaming endpoint and relays
    events directly to the mobile client.
    """
    from frappe_assistant_core.chat.fac_cloud_client import get_fac_cloud_client

    client = get_fac_cloud_client()
    if not client:
        yield _format_sse_event(
            "stream_error",
            {"error": _not_registered_error(), "action_required": "register"},
        )
        return

    # AR is addressed by the email identity (not the raw docname).
    ar_user = _ar_user_id(frappe.session.user)
    full_response = ""
    tokens_used = 0
    model_used = ""

    # Emit start event
    yield _format_sse_event("stream_start", {"session_id": session_id})

    try:
        # Stream from AR
        for event in client.stream_chat(
            session_id,
            message,
            ar_user,
            None,
            model_id,
            attachments,
            system_prompt_addendum,
            client_type="mobile",
        ):
            event_type = event.get("event")
            data = event.get("data", {})

            if event_type == "heartbeat":
                yield _format_sse_event("heartbeat", {"session_id": session_id})

            elif event_type == "stream_start":
                pass  # Already sent above

            elif event_type == "sources":
                # RAG citation sources — forward to native client for inline [N] rendering.
                yield _format_sse_event(
                    "sources",
                    {
                        "session_id": session_id,
                        "message_id": data.get("message_id"),
                        "sources": data.get("sources", []) or [],
                    },
                )

            elif event_type == "stream_chunk":
                chunk = data.get("content", "")
                full_response += chunk
                yield _format_sse_event(
                    "stream_chunk", {"session_id": session_id, "chunk": chunk, "accumulated": full_response}
                )

            # Reasoning Events (Thinking)
            elif event_type == "thinking":
                yield _format_sse_event(
                    "thinking", {"session_id": session_id, "content": data.get("content", "")}
                )

            elif event_type == "thinking_complete":
                yield _format_sse_event("thinking_complete", {"session_id": session_id})

            # Tool Execution Events
            elif event_type == "tool_call_start":
                yield _format_sse_event(
                    "tool_call_start",
                    {
                        "session_id": session_id,
                        "tool_name": data.get("tool_name"),
                        "tool_id": data.get("tool_id"),
                        "input": data.get("input", {}),
                    },
                )

            elif event_type in ("tool_result", "tool_call_result"):
                yield _format_sse_event(
                    "tool_call_result",
                    {
                        "session_id": session_id,
                        "tool_id": data.get("tool_id"),
                        "tool_name": data.get("tool_name"),
                        "result": data.get("result"),
                        "status": data.get("status", "success"),
                        "duration_ms": data.get("duration_ms"),
                    },
                )

            elif event_type == "tool_cancelled":
                yield _format_sse_event(
                    "tool_cancelled",
                    {
                        "session_id": session_id,
                        "tool_id": data.get("tool_id"),
                        "tool_name": data.get("tool_name"),
                        "message": data.get("message", "Cancelled"),
                    },
                )

            elif event_type == "stream_complete":
                tokens_used = data.get("tokens_used", 0)
                credits_used = data.get("credits_used", 0)
                model_used = data.get("model", "")
                routing = data.get("routing")
                full_response = data.get("full_response", full_response)

                # Log the conversation
                _log_conversation(
                    session_id, message, full_response, model_used, credits=credits_used, routing=routing
                )

                # Fold this turn's credits into the quota cache (credit units)
                _update_subscription_cache(credits_used)

                # Get quota info from cache
                from frappe_assistant_core.chat.quota_cache import get_quota_snapshot

                snap = get_quota_snapshot()
                quota_total = snap.get("quota_total", 0)
                is_unlimited = quota_total == -1
                quota_remaining = -1 if is_unlimited else max(0, quota_total - snap.get("quota_used", 0))

                yield _format_sse_event(
                    "stream_complete",
                    {
                        "session_id": session_id,
                        "full_response": full_response,
                        "quota_remaining": quota_remaining,
                        # This turn's own cost — parity with the web relay, and
                        # the only figure that moves an individually capped member.
                        "credits_used": credits_used,
                        "model_id": model_used,
                        "routing": routing,
                    },
                )

            elif event_type == "stream_error":
                # Strip + log the raw technical _detail server-side; the friendly
                # `error` field is what the app shows. Mirrors the web relay so
                # support gets diagnostics for mobile sessions too.
                from .chat.helpers import _log_stream_error_detail

                _log_stream_error_detail(data)
                yield _format_sse_event(
                    "stream_error",
                    {
                        "session_id": session_id,
                        "error": data.get("error", "Unknown error"),
                        "error_code": data.get("error_code", "UNKNOWN"),
                        "action_required": data.get("action_required"),
                    },
                )

    except Exception as e:
        import traceback

        error_msg = f"Error in mobile stream: {e!s}"
        frappe.log_error(title="FACO Mobile Stream Error", message=f"{error_msg}\n{traceback.format_exc()}")
        yield _format_sse_event(
            "stream_error", {"session_id": session_id, "error": _safe_error(e, "FACO Mobile Stream Error")}
        )

    finally:
        frappe.db.commit()  # nosemgrep: frappe-manual-commit — background thread / streaming context (not a request handler), explicit commit required to flush progress to DB.


def _format_sse_event(event_type, data):
    """
    Format data as an SSE event string.

    Args:
            event_type: The event type (e.g., 'stream_chunk', 'tool_call_start')
            data: Dictionary of event data

    Returns:
            str: Formatted SSE event string
    """
    json_data = json.dumps({"event": event_type, "data": data}, ensure_ascii=False)
    return f"event: {event_type}\ndata: {json_data}\n\n"


def _extract_file_attachments(message_name: str) -> str:
    """Extract content from files attached to a FACO Message."""
    try:
        attached_files = frappe.get_all(
            "File",
            filters={"attached_to_doctype": "FAC Chat Message", "attached_to_name": message_name},
            fields=["name", "file_name", "file_url", "file_size"],
        )

        if not attached_files:
            return ""

        try:
            from frappe_assistant_core.plugins.data_science.tools.extract_file_content import (
                ExtractFileContent,
            )

            extractor = ExtractFileContent()
        except ImportError:
            return ""

        file_contents = ["[Attached Files]"]

        for file_info in attached_files:
            try:
                result = extractor.execute({"file_url": file_info.file_url, "operation": "extract"})

                if result.get("success") and result.get("content"):
                    size_bytes = file_info.file_size or 0
                    if size_bytes < 1024:
                        size_str = f"{size_bytes} B"
                    elif size_bytes < 1024 * 1024:
                        size_str = f"{size_bytes / 1024:.1f} KB"
                    else:
                        size_str = f"{size_bytes / (1024 * 1024):.1f} MB"

                    file_contents.append(f"\nFile: {file_info.file_name}")
                    file_contents.append(f"Size: {size_str}")
                    file_contents.append("Content:")
                    file_contents.append(result["content"])
                    file_contents.append("-" * 80)

            except Exception as e:
                frappe.log_error(
                    title="FACO File Extraction",
                    message=f"Error extracting file {file_info.file_name}: {e!s}",
                )

        return "\n".join(file_contents) if len(file_contents) > 1 else ""

    except Exception as e:
        frappe.log_error(
            title="FACO File Extraction Error", message=f"Error in _extract_file_attachments: {e!s}"
        )
        return ""


def _log_conversation(session_id, message, response, model, credits=None, routing=None):
    """Log assistant response as a FACO Message. Credits-only — FAC never
    surfaces token counts (AR records those on AR Message)."""
    try:
        from frappe_assistant_core.chat.doctype.fac_chat_message.fac_chat_message import (
            FACChatMessage,
        )

        llm_metadata = {
            # Real model only; empty when unknown. Never the "ar-agent" placeholder.
            "model": model or None,
            "credits_used": credits,
            "routing": routing,
        }

        FACChatMessage.create_message(
            session_id=session_id, role="assistant", content=response, context=None, llm_metadata=llm_metadata
        )
        frappe.db.commit()  # nosemgrep: frappe-manual-commit — background thread / streaming context (not a request handler), explicit commit required to flush progress to DB.

    except Exception as e:
        frappe.log_error(title="FACO Mobile Log Error", message=f"Error logging conversation: {e!s}")


def _update_subscription_cache(credits_used):
    """Fold this turn's credits into the quota cache and trigger sync if stale.

    quota_used is credit-denominated (mirrors AR's credits_used), so pass the
    turn's credits_used — never the raw token count.
    """
    try:
        from frappe_assistant_core.chat.quota_cache import get_field, increment_used

        increment_used(credits_used)

        last_sync = get_field("last_sync", "")
        if last_sync:
            from frappe.utils import now, time_diff_in_hours

            hours_since_sync = time_diff_in_hours(now(), last_sync)
            if hours_since_sync > 12:
                frappe.enqueue(
                    "frappe_assistant_core.chat.api.billing.sync_subscription_status",
                    queue="short",
                    deduplicate=True,
                    job_id="sync-subscription-status",
                )
    except Exception as e:
        frappe.log_error(title="FACO Cache Error", message=f"Error updating subscription cache: {e!s}")


# ============================================================================
# Additional Mobile-Specific Endpoints
# ============================================================================


@frappe.whitelist(methods=["GET"])
def get_sessions(limit: int = 50, offset: int = 0) -> dict:
    """
    Get user's chat sessions for mobile conversation history.

    Optimized for mobile with pagination support.

    Args:
            limit: Maximum sessions to return (default 50, max 100)
            offset: Pagination offset

    Returns:
            dict: {sessions: [...], has_more: bool}
    """
    try:
        user = frappe.session.user
        limit = min(int(limit), 100)
        offset = int(offset)

        # Get session summaries using Frappe Query Builder
        FACChatMessage = frappe.qb.DocType("FAC Chat Message")

        session_query = (
            frappe.qb.from_(FACChatMessage)
            .select(
                FACChatMessage.session_id,
                Min(FACChatMessage.creation).as_("started"),
                Max(FACChatMessage.creation).as_("last_activity"),
                Count("*").as_("message_count"),
            )
            .where(FACChatMessage.user == user)
            .groupby(FACChatMessage.session_id)
            .orderby("last_activity", order=frappe.qb.desc)
            .limit(limit + 1)
            .offset(offset)
        )
        sessions = session_query.run(as_dict=True)

        has_more = len(sessions) > limit
        if has_more:
            sessions = sessions[:limit]

        # Fetch the first user message for each session as a preview
        session_ids = [s["session_id"] for s in sessions]
        previews: dict[str, str] = {}
        if session_ids:
            first_messages = frappe.get_all(
                "FAC Chat Message",
                filters={
                    "session_id": ["in", session_ids],
                    "user": user,
                    "role": "user",
                },
                fields=["session_id", "content"],
                order_by="creation asc",
            )
            # Keep only the first message per session
            for msg in first_messages:
                if msg.session_id not in previews:
                    content = (msg.content or "")[:100]
                    previews[msg.session_id] = content + ("..." if len(msg.content or "") > 100 else "")

        for session in sessions:
            session["preview"] = previews.get(session["session_id"], _("New conversation"))

        return {"sessions": sessions, "has_more": has_more}

    except Exception as e:
        frappe.log_error(title="FACO Mobile Sessions Error", message=f"Error getting mobile sessions: {e!s}")
        return {"sessions": [], "has_more": False, "error": _safe_error(e, "FACO Mobile Sessions Error")}


@frappe.whitelist(methods=["GET"])
def get_messages(session_id: str, limit: int = 100, offset: int = 0) -> dict:
    """
    Get messages for a session.

    Optimized for mobile with pagination.

    Args:
            session_id: The session ID
            limit: Maximum messages to return
            offset: Pagination offset

    Returns:
            dict: {messages: [...], has_more: bool}
    """
    try:
        user = frappe.session.user
        limit = min(int(limit), 500)
        offset = int(offset)

        # Ownership check — session_id is client-supplied and MUST be verified
        # against the caller's own messages to prevent cross-user IDOR.
        if not frappe.db.exists("FAC Chat Message", {"session_id": session_id, "user": user}):
            frappe.throw(_("Session not found"), frappe.PermissionError)

        messages = frappe.get_all(
            "FAC Chat Message",
            filters={"session_id": session_id, "user": user},
            fields=["name", "role", "content", "creation", "model", "credits_used", "routing"],
            order_by="creation asc",
            limit_page_length=limit + 1,
            limit_start=offset,
        )

        has_more = len(messages) > limit
        if has_more:
            messages = messages[:limit]

        # Format messages for mobile
        formatted = []
        for msg in messages:
            metadata = None
            # A zero-credit turn — cached, errored, or a free model — still has
            # a receipt worth showing. The old guard returned None and dropped it.
            if msg.model or msg.credits_used or msg.routing:
                metadata = {
                    "model": msg.model,
                    "credits_used": msg.credits_used,
                    "routing": msg.routing,
                }

            formatted.append(
                {
                    "id": msg.name,
                    "role": msg.role,
                    "content": msg.content or "",
                    "timestamp": str(msg.creation),
                    "metadata": metadata,
                }
            )

        return {"messages": formatted, "has_more": has_more}

    except frappe.PermissionError:
        # Surface as 403 instead of burying in a generic error payload
        raise
    except Exception as e:
        frappe.log_error(title="FACO Mobile Messages Error", message=f"Error getting mobile messages: {e!s}")
        return {"messages": [], "has_more": False, "error": _safe_error(e, "FACO Mobile Messages Error")}


@frappe.whitelist(methods=["GET"])
def search_sessions(query: str, limit: int = 20) -> list:
    """
    Search chat sessions by message content.

    Args:
            query: Search query string
            limit: Maximum results (default 20)

    Returns:
            list: Matching sessions with preview, message_count, match_context
    """
    try:
        user = frappe.session.user
        limit = min(int(limit), 50)

        if not query or len(query) < 2:
            return []

        # FACO-M12: cap query length and neutralize LIKE wildcards. A
        # megabyte-scale query would force a pathological scan of every
        # FACO Message row the user owns, and ``%``/``_`` are promoted into
        # SQL wildcards by frappe.get_all — escape them so search matches
        # the user's literal intent.
        query = str(query)[:200]
        safe_query = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")

        # Find messages matching the query
        matching_messages = frappe.get_all(
            "FAC Chat Message",
            filters={
                "user": user,
                "content": ["like", f"%{safe_query}%"],
            },
            fields=["session_id", "content", "creation"],
            order_by="creation desc",
        )

        # Deduplicate by session_id, keeping the first (most recent) match
        seen_sessions: set[str] = set()
        unique_matches: list[dict] = []
        for msg in matching_messages:
            if msg.session_id not in seen_sessions:
                seen_sessions.add(msg.session_id)
                unique_matches.append(msg)
            if len(unique_matches) >= limit:
                break

        if not unique_matches:
            return []

        session_ids = [m["session_id"] for m in unique_matches]

        # Get session metadata (last_activity + message_count) via Query Builder
        FACChatMessage = frappe.qb.DocType("FAC Chat Message")
        session_stats = (
            frappe.qb.from_(FACChatMessage)
            .select(
                FACChatMessage.session_id,
                Max(FACChatMessage.creation).as_("last_activity"),
                Count("*").as_("message_count"),
            )
            .where((FACChatMessage.user == user) & (FACChatMessage.session_id.isin(session_ids)))
            .groupby(FACChatMessage.session_id)
        ).run(as_dict=True)

        stats_map: dict[str, dict] = {s["session_id"]: s for s in session_stats}

        # Get first user message per session for preview
        first_messages = frappe.get_all(
            "FAC Chat Message",
            filters={
                "session_id": ["in", session_ids],
                "user": user,
                "role": "user",
            },
            fields=["session_id", "content"],
            order_by="creation asc",
        )
        preview_map: dict[str, str] = {}
        for msg in first_messages:
            if msg.session_id not in preview_map:
                content = (msg.content or "")[:100]
                preview_map[msg.session_id] = content + ("..." if len(msg.content or "") > 100 else "")

        # Build results with match context
        formatted = []
        for match in unique_matches:
            sid = match["session_id"]
            stats = stats_map.get(sid, {})
            preview = preview_map.get(sid, _("Conversation"))

            # Extract context around the match
            matched_content = (match.get("content") or "")[:200]
            match_context = None
            if matched_content:
                query_lower = query.lower()
                content_lower = matched_content.lower()
                pos = content_lower.find(query_lower)
                if pos >= 0:
                    start = max(0, pos - 30)
                    end = min(len(matched_content), pos + len(query) + 50)
                    match_context = matched_content[start:end]

            formatted.append(
                {
                    "session_id": sid,
                    "preview": preview,
                    "last_activity": stats.get("last_activity"),
                    "message_count": stats.get("message_count", 0),
                    "match_context": match_context,
                }
            )

        # Sort by last_activity descending
        formatted.sort(key=lambda x: x.get("last_activity") or "", reverse=True)
        return formatted

    except Exception as e:
        frappe.log_error(title="FACO Mobile Search Error", message=f"Error searching sessions: {e!s}")
        return []


@frappe.whitelist(methods=["GET"])
def get_available_models() -> list:
    """
    Get list of available AI models for the user.

    Returns:
            list: Available models with id, name, description
    """
    try:
        from frappe_assistant_core.chat.fac_cloud_client import get_fac_cloud_client

        client = get_fac_cloud_client()
        if not client:
            return []

        # Get models from AR
        result = client.get_available_models(user_id=_ar_user_id(frappe.session.user))

        if result and result.get("models"):
            return result["models"]

        return []

    except Exception as e:
        frappe.log_error(title="FACO Mobile Models Error", message=f"Error getting models: {e!s}")
        return []
