# Frappe Assistant Core - Chat Internal Helpers
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Internal helpers shared by messaging and AR-relay paths.

None of these are whitelisted endpoints — they're called from the
streaming background-thread relay and the send/resume request handlers.
"""

from __future__ import annotations

import frappe


def _is_processing_restricted(user: str | None = None) -> bool:
    """FACO-M15: return True when the user has set GDPR Art. 18 restriction.

    Reads the local mirror on FACO User Preferences (kept in sync by
    ``privacy.restrict_my_processing``). Defaults to False (persist normally)
    when the preferences row doesn't exist or the column hasn't been migrated
    yet — fail-open is the right call here because the alternative is to
    silently drop chat history for every user on upgrade day.
    """
    user = user or frappe.session.user
    if not user or user == "Guest":
        return False
    try:
        flag = frappe.db.get_value("FAC Chat User Preferences", user, "processing_restricted")
        return bool(flag)
    except Exception:
        return False


def _emit_socket_event(session_id, data):
    """Emit a Socket.IO event scoped to a single session room.

    Clients (widget + SPA) join the matching ``task_progress:<id>`` room via
    Frappe's ``task_subscribe`` socket event when they start a session, so
    events for one tab/conversation never reach other tabs the same user has
    open. We pass ``room=`` directly (rather than ``task_id=``) because it is
    more explicit about scoping — these aren't real background tasks.
    """
    try:
        frappe.publish_realtime(
            event="faco_message_stream",
            message=data,
            room=f"task_progress:{session_id}",
            after_commit=False,
        )
    except Exception as e:
        frappe.log_error(title="FACO Socket Error", message=f"Error emitting socket event: {e!s}")


def _log_stream_error_detail(data: dict) -> None:
    """Record that a stream_error happened, without cloud-service internals.

    The upstream payload may include ``_detail`` (raw exception text). That
    string is stripped here so it never reaches the SPA *or* the tenant
    Error Log — table names like ``tabAR Tenant User`` are a leak. The
    friendly ``error`` field is what users see; Error Log keeps only the
    stable ``error_code``.
    """
    had_detail = "_detail" in data
    data.pop("_detail", None)
    if not had_detail:
        return
    code = data.get("error_code", "UNKNOWN")
    from .._helpers import _log, _summarize_stream_error_for_log

    _log(
        title=f"FAC Chat stream error: {code}",
        detail=_summarize_stream_error_for_log(code),
    )


def _attach_files_to_message(file_urls: list[str], message_name: str) -> int:
    """Link composer uploads to the persisted user message. Returns the count linked.

    Ownership scoping is the security boundary here: ``get_all`` bypasses
    permissions, so without ``owner`` any caller could name an arbitrary private
    ``file_url`` and have ``_extract_file_attachments`` read it into the prompt.

    Clearing ``fac_pending_chat_attachment`` is what takes the file out of the
    orphan sweep's reach — uploads are flagged on selection, not on send.
    """
    file_docs = frappe.get_all(
        "File",
        filters={"file_url": ["in", file_urls], "owner": frappe.session.user},
        fields=["name", "file_url"],
        limit_page_length=0,
    )

    linked = 0
    for file_doc in file_docs:
        try:
            frappe.db.set_value(
                "File",
                file_doc.name,
                {
                    "attached_to_doctype": "FAC Chat Message",
                    "attached_to_name": message_name,
                    "fac_pending_chat_attachment": 0,
                },
                update_modified=False,
            )
            linked += 1
        except Exception as e:
            frappe.log_error(
                title="FACO File Attachment Error",
                message=f"Error attaching file {file_doc.file_url}: {e!s}",
            )

    frappe.db.commit()  # nosemgrep: frappe-manual-commit — background thread / streaming context (not a request handler), explicit commit required to flush progress to DB.
    return linked


def _extract_file_attachments(message_name: str) -> str:
    """
    Extract content from files attached to a FACO Message.

    Uses the ExtractFileContent tool from frappe_assistant_core.
    """
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
            frappe.log_error(title="FACO File Extraction", message="frappe_assistant_core not installed")
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


def _prepare_prompt(message: str, context: dict, include_context: bool) -> str:
    """
    Prepare the full prompt with optional context.

    DEPRECATED: This function is no longer used as context is now fetched
    on-demand by the LLM using browser_get_page_context tool.
    Kept for backwards compatibility.
    """
    if not include_context or not context:
        return message

    context_type = context.get("type")
    screen_content = context.get("screen_content", "")

    context_templates = {
        "Form": """
Current Page Context:
- Type: Form
- DocType: {doctype}
- Document Name: {name}
- URL: {url}

{screen_content}
""",
        "List": """
Current Page Context:
- Type: List View
- DocType: {doctype}
- URL: {url}

{screen_content}
""",
        "Report": """
Current Page Context:
- Type: Report
- Report Name: {name}
- Active Filters: {filters}
- URL: {url}

{screen_content}

The user is viewing this report. You can use tools to execute this report with modified filters.
""",
        "Tree": """
Current Page Context:
- Type: Tree View
- DocType: {doctype}
- URL: {url}

{screen_content}
""",
        "Workspace": """
Current Page Context:
- Type: Workspace
- Workspace Name: {workspace_name}
- URL: {url}

{screen_content}
""",
        "Dashboard": """
Current Page Context:
- Type: Dashboard
- Dashboard Name: {dashboard_name}
- URL: {url}

{screen_content}
""",
    }

    template = context_templates.get(
        context_type,
        """
Current Page Context:
- Type: {type}
- URL: {url}

{screen_content}
""",
    )

    # Build context string
    filters = context.get("filters", {})
    filters_str = frappe.as_json(filters, indent=2) if filters else "None"

    context_str = template.format(
        type=context_type or "General",
        doctype=context.get("doctype", ""),
        name=context.get("name", ""),
        url=context.get("url", ""),
        workspace_name=context.get("workspace_name", ""),
        dashboard_name=context.get("dashboard_name", ""),
        filters=filters_str,
        screen_content=screen_content or "Page view",
    )

    return f"{message}\n\n{context_str}"


def _find_assistant_msg_by_message_id(session_id: str, message_id: str) -> str | None:
    """Find the FACO Message row for a specific assistant turn, keyed on AR's message_id.

    message_id is AR's per-turn identifier and stays stable across HITL
    interrupt/resume cycles within the same turn (AR reuses it). This
    avoids the "find most recent assistant row" trap that appended resume
    output to the wrong turn after a prior completed turn's row became the
    most recent. Returns the FACO Message `name` or None.
    """
    if not message_id:
        return None
    return frappe.db.get_value(
        "FAC Chat Message",
        {"session_id": session_id, "role": "assistant", "message_id": message_id},
        "name",
    )


def _ensure_assistant_msg(session_id: str, message_id: str, context: dict | None = None) -> str | None:
    """Create the assistant FACO Message row early so resumes can find it by message_id.

    Called on ``stream_start`` in ``_relay_ar_stream``. The row begins with
    empty content and is updated in place when ``stream_complete`` fires
    (even if the stream ends with ``interrupted=True``, a row exists for
    the next resume to find). Idempotent — returns an existing row if one
    is already keyed on this message_id.
    """
    if not message_id:
        return None

    existing = _find_assistant_msg_by_message_id(session_id, message_id)
    if existing:
        return existing

    try:
        from frappe_assistant_core.chat.doctype.fac_chat_message.fac_chat_message import (
            FACChatMessage,
        )

        msg = FACChatMessage.create_message(
            session_id=session_id,
            role="assistant",
            content="",
            context=context,
        )
        if msg and message_id:
            frappe.db.set_value("FAC Chat Message", msg.name, "message_id", message_id)
            frappe.db.commit()  # nosemgrep: frappe-manual-commit — background thread / streaming context (not a request handler), explicit commit required to flush progress to DB.
            return msg.name
    except Exception as e:
        frappe.log_error(title="FACO Log Error", message=f"Error ensuring assistant message row: {e!s}")
    return None


def _log_conversation(
    session_id,
    message,
    response,
    model,
    context,
    tool_calls=None,
    message_id=None,
    blocks=None,
    credits=None,
    model_breakdown=None,
):
    """Log assistant response as a FACO Message, including tool calls and blocks snapshot."""
    # FACO-M15: when processing is restricted, don't persist the assistant
    # turn either. The resume/interrupt paths already tolerate a missing row.
    # Resolve the session owner via any existing FACO Message for this session;
    # if the user stream never persisted one (also due to M15) we fall back to
    # ``frappe.session.user`` which is correct inside the streaming thread
    # because Frappe re-binds it from ``user`` argument.
    try:
        owner = (
            frappe.db.get_value(
                "FAC Chat Message",
                {"session_id": session_id},
                "user",
            )
            or frappe.session.user
        )
        if _is_processing_restricted(owner):
            return
    except Exception:
        # Never let the consent check crash the logger.
        pass

    try:
        import json as json_module

        from frappe_assistant_core.chat.doctype.fac_chat_message.fac_chat_message import (
            FACChatMessage,
        )

        llm_metadata = {
            # Real model only; empty when unknown (UI hides the chip). Never the
            # old "ar-agent" placeholder.
            "model": model or None,
            "credits_used": credits,
        }

        msg = FACChatMessage.create_message(
            session_id=session_id,
            role="assistant",
            content=response,
            context=context,
            llm_metadata=llm_metadata,
        )

        if msg:
            updates = {}
            if tool_calls:
                updates["tool_calls"] = json_module.dumps(tool_calls)
            if message_id:
                updates["message_id"] = message_id
            if blocks:
                updates["blocks"] = json_module.dumps(blocks)
            if model_breakdown:
                updates["model_breakdown"] = json_module.dumps(model_breakdown)
            if updates:
                for field, value in updates.items():
                    frappe.db.set_value("FAC Chat Message", msg.name, field, value)

        frappe.db.commit()  # nosemgrep: frappe-manual-commit — background thread / streaming context (not a request handler), explicit commit required to flush progress to DB.

    except Exception as e:
        frappe.log_error(title="FACO Log Error", message=f"Error logging conversation: {e!s}")


def _update_subscription_cache(credits_used):
    """Fold this turn's credits into the quota cache and trigger sync if stale.

    quota_used mirrors AR's credit-denominated credits_used, so the caller must
    pass the turn's credits_used — NOT the raw token count. Passing tokens made
    the header credit meter read as exhausted after a single message.
    """
    try:
        from frappe_assistant_core.chat.quota_cache import get_field, increment_used

        increment_used(credits_used)

        # Trigger background sync if cache is stale (>12 hours since last sync)
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
