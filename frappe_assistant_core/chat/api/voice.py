# Frappe Assistant Core - Voice Proxy API
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Voice-to-text proxy. Forwards browser audio to AR via the SDK.

Gates the call on FAC Chat being enabled and the caller being a FACO
member. Returns whatever AR returns (text, duration, credits).
"""

from __future__ import annotations

import frappe
from frappe import _

from frappe_assistant_core.chat.gate import is_chat_enabled

from .auth import _ar_user_id

MAX_AUDIO_BYTES = 1_048_576  # 1 MB — mirrors AR


def _user_can_use_faco() -> bool:
    """True if the user may use FACO — authoritative AR membership, matching
    can_use_faco. Membership (a seat), not Frappe role, gates USE.
    """
    from frappe_assistant_core.chat.api.settings.access import _is_faco_member

    return _is_faco_member(frappe.session.user)


@frappe.whitelist(methods=["POST"])
def transcribe(duration_ms: int = 0, language: str | None = None) -> dict:
    """Proxy voice transcription to AR via SDK.

    Args:
        duration_ms: Client-reported audio duration (advisory).
        language: ISO-639-1 hint ("en", "es"…) from the caller. Forwarded
            verbatim to AR; suppresses Whisper's cross-language hallucinations
            on short / silent clips. Falls back to the user's Frappe language
            preference, then English, when omitted.

    Returns:
        {"text": str, "duration_seconds": float, "credits_consumed": float}
    """
    if not is_chat_enabled():
        frappe.throw(_("FAC Chat is disabled."), frappe.PermissionError)
    if not _user_can_use_faco():
        frappe.throw(_("You are not enabled for FACO."), frappe.PermissionError)

    audio_file = frappe.request.files.get("audio")
    if not audio_file:
        frappe.throw(_("No audio file provided."), frappe.ValidationError)

    audio_bytes = audio_file.read()
    if not audio_bytes:
        frappe.throw(_("Audio file is empty."), frappe.ValidationError)
    if len(audio_bytes) > MAX_AUDIO_BYTES:
        frappe.throw(
            _("Audio file too large ({0} bytes, max {1}).").format(len(audio_bytes), MAX_AUDIO_BYTES),
            frappe.ValidationError,
        )

    mime_type = audio_file.mimetype or "audio/webm"

    lang = (language or "").strip() or _resolve_default_language()

    from frappe_assistant_core.chat.fac_cloud_client import get_fac_cloud_client

    client = get_fac_cloud_client()
    if not client:
        frappe.throw(
            _("FACO is not registered with FAC Cloud. Please register first."),
            frappe.ValidationError,
        )

    return client.transcribe_audio(
        audio_bytes=audio_bytes,
        mime_type=mime_type,
        user_id=_ar_user_id(frappe.session.user),
        duration_ms=int(duration_ms or 0),
        language=lang,
    )


def _resolve_default_language() -> str:
    """Fallback used only when the client sent no language hint.

    The browser sends `navigator.language` (and the SPA also reads the
    AR Tenant User profile locale ahead of that). If neither is present —
    a non-browser SDK caller, a stripped form, or a request from an iframe
    that lost its locale — fall back to English. Whisper's auto-detect on
    silent audio is the failure mode we're trying to avoid.
    """
    return "en"
