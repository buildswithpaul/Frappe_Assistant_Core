# Frappe Assistant Core - Send / Resume Message API
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Whitelisted endpoints that initiate or resume an AR chat stream.

Both endpoints save state synchronously, then submit the SSE relay to
the bounded background pool defined in this module. The relay itself
lives in ``relay.py``.
"""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor

import frappe
from frappe import _

from .._rate_limits import (
    rate_limit,
    session_user_or_ip,
)
from .._untrusted import wrap_untrusted
from ..chat.helpers import (
    _attach_files_to_message,
    _extract_file_attachments,
    _is_processing_restricted,
)
from ..chat.relay import (
    _relay_ar_interrupt_resume,
    _relay_ar_stream,
)

# Bounded thread pool for relaying AR SSE streams to Socket.IO. Replaces
# unbounded ``threading.Thread`` spawning (FACO-H14). Workers are daemon
# so they don't block process shutdown. Overflow currently queues inside
# the executor — bounded-queue rejection is a documented follow-up.
_relay_pool = ThreadPoolExecutor(max_workers=20, thread_name_prefix="faco-relay")


def _flag(value) -> bool:
    """Coerce a composer toggle to a real bool.

    The SPA posts JSON so this arrives as a bool, but the Desk widget calls the
    same endpoint form-encoded, where it arrives as the string "true"/"false".
    """
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes")
    return bool(value)


_MAX_SIGNAL_COUNT = 999
_MAX_SIGNAL_AGE_S = 3600


def _clamp_int(value, maximum: int = _MAX_SIGNAL_COUNT) -> int:
    """Coerce a client-supplied count to a sane int. Anything odd becomes 0.

    ``int(float('inf'))`` raises ``OverflowError``, not ``ValueError`` — a bare
    ``Infinity`` JSON token (which ``json.loads`` accepts by default) reaches
    here as exactly that float, so it must be caught alongside the usual
    TypeError/ValueError from a non-numeric value.
    """
    try:
        number = int(value)
    except (TypeError, ValueError, OverflowError):
        return 0
    return max(0, min(number, maximum))


def _render_client_signals(raw) -> str:
    """Turn client-reported browser signals into a fixed sentence.

    The client supplies COUNTS ONLY. The wording is owned here so a hand-rolled
    or compromised caller cannot write prose into the system prompt — which is
    what passing the sentence itself would allow.

    This function's entire job is to be exception-proof against a
    client-controlled string reaching a message the user has already had
    persisted — a blanket guard backs the specific ones below.
    """
    try:
        return _render_client_signals_unguarded(raw)
    except Exception:
        return ""


def _render_client_signals_unguarded(raw) -> str:
    if not raw:
        return ""

    data = raw
    if isinstance(data, str):
        try:
            data = json.loads(data)
        # ValueError, not just JSONDecodeError: an oversized bare integer
        # literal (4300+ digits) trips CPython's int-string-conversion guard
        # inside json.loads itself as a plain ValueError.
        except ValueError:
            return ""
    if not isinstance(data, dict):
        return ""

    errors = data.get("recent_errors")
    if not isinstance(errors, dict):
        return ""

    console = _clamp_int(errors.get("console"))
    failed = _clamp_int(errors.get("failed_requests"))
    if not console and not failed:
        return ""

    age = _clamp_int(errors.get("newest_age_s"), maximum=_MAX_SIGNAL_AGE_S)

    return (
        "\n\n## Browser Signals\n\n"
        f"The user's browser has recorded {console} console error(s) and "
        f"{failed} failed network request(s) in the recent past "
        f"(most recent about {age}s ago). "
        "If their message concerns something not working, call "
        "`browser_capture_diagnostics` before answering — it returns the "
        "error type and the server's error message (the traceback too, when "
        "available) behind those counts. This is the expected first action, "
        "not an extra tool call."
    )


def _assert_session_owner(session_id: str) -> None:
    """Refuse to drive a conversation the caller does not own.

    Mirrors the check in ``cancel_stream``. A session with no persisted
    messages has no owner to compare against (zero retention, or M15
    processing restriction), so it passes.
    """
    owner = frappe.db.get_value(
        "FAC Chat Message",
        {"session_id": session_id},
        "user",
        order_by="creation desc",
    )
    if owner and owner != frappe.session.user and "System Manager" not in frappe.get_roles():
        frappe.throw(_("You can only continue your own conversation"), frappe.PermissionError)


@frappe.whitelist(methods=["POST"])
@rate_limit(session_user_or_ip, limit=30, seconds=60)
def send_message(
    session_id: str,
    message: str,
    context: str | None = None,
    include_context: bool = True,
    file_urls: str | None = None,
    model_id: str | None = None,
    attachments: str | None = None,
    system_prompt_addendum: str | None = None,
    client_type: str | None = None,
    web_search: bool | None = None,
    thinking_enabled: bool | None = None,
    client_signals: str | None = None,
) -> dict:
    """
    Send a message to FACO and stream AI response via Socket.IO.

    This endpoint saves the user message, then spawns a background thread
    that relays the SSE stream from AR to the frontend via Socket.IO.

    Args:
            session_id (str): Conversation session ID
            message (str): User's message
            context (str): JSON string of page context (deprecated - LLM uses browser tools instead)
            include_context (bool): Whether to include page context in prompt (deprecated)
            file_urls (str): JSON array of file URLs to attach
            model_id (str): Optional model ID to use for this request (per-request model selection)
            attachments (str): JSON array of attachments for Vision API
                    Each: {type: "image", format: "png|jpeg|...", data: "<base64>", name: "...", file_url: "..."}
            system_prompt_addendum (str): Optional per-request addition to the system prompt (e.g., onboarding mode)
            web_search (bool): Composer toggle for AR web search. Defaults to None — absence must
                    reach AR as absence (AR treats it as "search available"), not as an explicit
                    off; only a caller-supplied True/False turns it on/off. May arrive as "true"/
                    "false" strings from the form-encoded Desk widget; coerced via ``_flag``.
            thinking_enabled (bool): Composer toggle for AR extended thinking. Same None-vs-explicit
                    semantics and coercion as web_search.
            client_signals (str): JSON of counts-only browser signals from the widget,
                    e.g. {"recent_errors": {"console": 2, "failed_requests": 1,
                    "newest_age_s": 4}}. Counts are read; any other content is ignored.
                    The rendered wording is owned by the server, never the client.

    Returns:
            dict: Acknowledgment that processing has started
    """
    try:
        # Parse context if provided as string (for backwards compatibility)
        if isinstance(context, str):
            context = json.loads(context) if context else {}

        # Parse file_urls if provided as string
        if isinstance(file_urls, str):
            file_urls = json.loads(file_urls) if file_urls else []
        if not file_urls:
            file_urls = []
        else:
            file_urls = list(dict.fromkeys(file_urls))  # Deduplicate preserving order

        # Parse attachments if provided as string (for Vision API)
        if isinstance(attachments, str):
            attachments = json.loads(attachments) if attachments else []
        if not attachments:
            attachments = []

        _assert_session_owner(session_id)

        # Check if user can use FACO
        from ..settings import can_use_faco

        access_check = can_use_faco()
        if not access_check.get("can_use"):
            frappe.throw(access_check.get("reason", _("Cannot use FACO")))

        # FACO-M15: respect GDPR Article 18 processing restriction. When set,
        # skip message persistence entirely — the chat still runs (AR handles
        # the turn in-memory), but no content survives in FACO Message.
        restricted = _is_processing_restricted(frappe.session.user)

        # Save user message to database
        from frappe_assistant_core.chat.doctype.fac_chat_message.fac_chat_message import (
            FACChatMessage,
        )

        user_msg = None
        if not restricted:
            user_msg = FACChatMessage.create_message(
                session_id=session_id,
                role="user",
                content=message,
                context=context if include_context and context else None,
            )
            frappe.db.commit()  # nosemgrep: frappe-manual-commit — background thread / streaming context (not a request handler), explicit commit required to flush progress to DB.

        # Attach files to the message — only meaningful when we persisted one.
        if file_urls and user_msg is not None:
            _attach_files_to_message(file_urls, user_msg.name)

        # Prepare prompt - send the original user message to AR (not enriched with file content)
        # File content goes via system_prompt_addendum so it reaches the LLM without polluting
        # the stored user message in conversation history.
        full_prompt = message

        # File attachments depend on a persisted user message row. When the
        # user has restricted processing (M15), we don't persist, so there
        # is nothing to enrich — AR processes the prompt as-is.
        if user_msg is not None:
            file_content = _extract_file_attachments(user_msg.name)
            if file_content:
                # Wrap file content in an untrusted envelope so the LLM treats
                # it as data, not instructions (FACO-H15 prompt injection).
                file_addendum = wrap_untrusted(file_content, kind="user_attached_files")
                system_prompt_addendum = (system_prompt_addendum or "") + file_addendum

        signal_addendum = _render_client_signals(client_signals)
        if signal_addendum:
            system_prompt_addendum = (system_prompt_addendum or "") + signal_addendum

        # Default to "spa" if client_type not specified (fail-safe: blocks browser tools)
        effective_client_type = client_type or "spa"

        # Zero-retention: load the client-held session blob to round-trip to AR.
        # Skipped for restricted users — we never load or store their state.
        from frappe_assistant_core.chat.doctype.fac_chat_session_state.fac_chat_session_state import (
            FACChatSessionState,
        )

        session_state = None if restricted else FACChatSessionState.load_wire(session_id)

        # Process in background via bounded pool (FACO-H14) — relay from AR.
        # user_msg_name may be None under M15 restriction — relay tolerates.
        _relay_pool.submit(
            _relay_ar_stream,
            session_id,
            full_prompt,
            message,
            context,
            user_msg.name if user_msg is not None else None,
            frappe.session.user,
            frappe.local.site,
            model_id,
            attachments,
            system_prompt_addendum,
            effective_client_type,
            session_state,
            restricted,
            # None must reach AR as absence (search available), not as an explicit
            # off — only coerce when the caller actually supplied a value.
            web_search=_flag(web_search) if web_search is not None else None,
            thinking_enabled=_flag(thinking_enabled) if thinking_enabled is not None else None,
        )

        return {
            "status": "processing",
            "session_id": session_id,
            "message": _("Message is being processed. Response will be streamed via Socket.IO."),
        }

    # frappe.PermissionError does not subclass ValidationError, so the blanket
    # handler below would mask the ownership refusal as a generic error.
    except frappe.PermissionError:
        raise
    except Exception as e:
        frappe.log_error(title="FACO Agent Error", message=f"Error in send_message: {e!s}")
        frappe.throw(_("Error processing message: {0}").format(str(e)))


@frappe.whitelist(methods=["POST"])
@rate_limit(session_user_or_ip, limit=30, seconds=60)
def resume_interrupt(
    session_id: str,
    interrupt_response: str,
    client_type: str | None = None,
    message_id: str | None = None,
    model_id: str | None = None,
    web_search: bool | None = None,
    thinking_enabled: bool | None = None,
) -> dict:
    """
    Resume a HITL-interrupted agent stream with the user's approval/rejection.

    Called after the frontend receives an ``approval_required`` event
    and the user clicks Approve / Reject / Trust.

    Args:
            session_id: Conversation session ID (same session that was interrupted)
            interrupt_response: JSON array of responses.
                    Each: {"interruptId": str, "response": "approve"|"rejected"|"trust"|"session"}
            client_type: Optional client type (widget/spa/mobile/api)
            model_id: Model the interrupted turn was sent with, carried so the
                    resume finishes on it. Sent only for an explicit user choice —
                    in auto mode it is omitted, never the literal "auto", because
                    the resume path skips classification and would hand AR a model
                    name that does not exist. None reaches AR as absence.
            web_search: Composer toggle for the conversation being resumed. Same
                    None-vs-explicit semantics and ``_flag`` coercion as
                    send_message — a resume that omits it reaches AR as absence,
                    which AR reads as "search available".
            thinking_enabled: Composer toggle for AR extended thinking, same rules.

    Returns:
            dict: Acknowledgment that resume processing has started
    """
    try:
        # Parse interrupt_response
        if isinstance(interrupt_response, str):
            interrupt_response = json.loads(interrupt_response) if interrupt_response else []

        if not interrupt_response:
            frappe.throw(_("interrupt_response is required"))

        _assert_session_owner(session_id)

        # Check access
        from ..settings import can_use_faco

        access_check = can_use_faco()
        if not access_check.get("can_use"):
            frappe.throw(access_check.get("reason", _("Cannot use FACO")))

        effective_client_type = client_type or "spa"

        # Zero-retention: load the client-held session blob to round-trip on
        # resume. Skipped for GDPR-restricted users (FACO-M15) — same rule as
        # send_message: never load or store their state.
        restricted = _is_processing_restricted(frappe.session.user)
        from frappe_assistant_core.chat.doctype.fac_chat_session_state.fac_chat_session_state import (
            FACChatSessionState,
        )

        session_state = None if restricted else FACChatSessionState.load_wire(session_id)

        # Resume in background via bounded pool (FACO-H14) — same relay
        # pattern as send_message.
        _relay_pool.submit(
            _relay_ar_interrupt_resume,
            session_id,
            interrupt_response,
            frappe.session.user,
            frappe.local.site,
            effective_client_type,
            message_id,
            session_state,
            restricted,
            # The turn the user approved was sent with these; the resume is the
            # same turn continuing, so it has to carry them too.
            model_id=model_id,
            web_search=_flag(web_search) if web_search is not None else None,
            thinking_enabled=_flag(thinking_enabled) if thinking_enabled is not None else None,
        )

        return {
            "status": "processing",
            "session_id": session_id,
            "message": _("Resuming agent with approval response."),
        }

    # frappe.PermissionError does not subclass ValidationError, so the blanket
    # handler below would mask the ownership refusal as a generic error.
    except frappe.PermissionError:
        raise
    except Exception as e:
        frappe.log_error(title="FACO Agent Error", message=f"Error in resume_interrupt: {e!s}")
        frappe.throw(_("Error resuming interrupt: {0}").format(str(e)))


@frappe.whitelist(methods=["POST"])
@rate_limit(session_user_or_ip, limit=30, seconds=60)
def continue_response(
    session_id: str,
    message_id: str,
    client_type: str | None = None,
    web_search: bool | None = None,
    thinking_enabled: bool | None = None,
) -> dict:
    """
    Continue a previously truncated assistant response (max_tokens stop).

    Called after the frontend receives a ``stream_complete`` event with
    ``truncated: true`` and the user clicks Continue. No new user message
    is sent — AR is asked to resume generation from ``message_id``, and
    the relay appends the continuation onto the same FACO Message row.

    Args:
            session_id: Conversation session ID (same session that was truncated)
            message_id: The AR message ID of the truncated assistant turn to continue
            client_type: Optional client type (widget/spa/mobile/api)
            web_search: Composer toggle for the conversation being continued. Same
                    None-vs-explicit semantics and ``_flag`` coercion as send_message.
            thinking_enabled: Composer toggle for AR extended thinking, same rules.

    Returns:
            dict: Acknowledgment that continuation processing has started
    """
    try:
        if not message_id:
            frappe.throw(_("message_id is required"))

        _assert_session_owner(session_id)

        # Check access
        from ..settings import can_use_faco

        access_check = can_use_faco()
        if not access_check.get("can_use"):
            frappe.throw(access_check.get("reason", _("Cannot use FACO")))

        effective_client_type = client_type or "spa"

        # Zero-retention: load the client-held session blob to round-trip on
        # continue. Skipped for GDPR-restricted users (FACO-M15) — same rule
        # as send_message / resume_interrupt: never load or store their state.
        restricted = _is_processing_restricted(frappe.session.user)
        from frappe_assistant_core.chat.doctype.fac_chat_session_state.fac_chat_session_state import (
            FACChatSessionState,
        )

        session_state = None if restricted else FACChatSessionState.load_wire(session_id)

        # Continue in background via bounded pool (FACO-H14) — reuses the
        # normal stream relay; continue_from_message_id tells it to skip
        # pushing a user message and ask AR to resume from message_id.
        _relay_pool.submit(
            _relay_ar_stream,
            session_id,
            full_prompt=None,
            original_message=None,
            context=None,
            message_name=None,
            user=frappe.session.user,
            site=frappe.local.site,
            client_type=effective_client_type,
            session_state=session_state,
            restricted=restricted,
            continue_from_message_id=message_id,
            # A continuation is the same turn finishing; it must run under the
            # same toggles, not fall back to AR's absence defaults.
            web_search=_flag(web_search) if web_search is not None else None,
            thinking_enabled=_flag(thinking_enabled) if thinking_enabled is not None else None,
        )

        return {
            "status": "processing",
            "session_id": session_id,
            "message": _("Continuing truncated response."),
        }

    # frappe.PermissionError does not subclass ValidationError, so the blanket
    # handler below would mask the ownership refusal as a generic error.
    except frappe.PermissionError:
        raise
    except Exception as e:
        frappe.log_error(title="FACO Agent Error", message=f"Error in continue_response: {e!s}")
        frappe.throw(_("Error continuing response: {0}").format(str(e)))
