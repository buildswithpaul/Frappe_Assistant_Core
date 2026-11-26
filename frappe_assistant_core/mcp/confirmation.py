# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License

"""
Signed, single-use consent for destructive MCP tool calls (MRTR elicitation).

The first call returns an ``input_required`` result whose ``requestState`` is a token bound to
the user, the tool and a digest of the arguments. The retry carries the token back with the
user's answer; ``consume_state`` accepts it once, before it expires, for exactly that call.

Token: ``base64url(JSON payload) + "." + base64url(HMAC-SHA256(payload segment))``.
"""

import base64
import hashlib
import hmac
import json
import secrets
from typing import Optional

import frappe
import redis
from frappe import _
from frappe.utils import now_datetime
from frappe.utils.password import get_encryption_key

from frappe_assistant_core.mcp.protocol import ERR_INVALID_PARAMS, ProtocolError
from frappe_assistant_core.utils.mcp_caller import request_is_from_fac_cloud

STATE_TTL_SECONDS = 600
INPUT_KEY = "confirm"

_KEY_LABEL = b"fac-mcp-consent-v1"
_NONCE_CACHE_PREFIX = "fac_mcp_consent_nonce:"
_PAYLOAD_FIELDS = {"user": str, "tool": str, "args_sha256": str, "exp": int, "nonce": str}


class ConsentRefused(Exception):
    """The request state is invalid, expired, already used, or for a different call."""


def issue_state(user: str, tool: str, arguments: dict) -> str:
    return _sign(
        {
            "user": user,
            "tool": tool,
            "args_sha256": _arguments_digest(arguments),
            "exp": _now_timestamp() + STATE_TTL_SECONDS,
            "nonce": secrets.token_urlsafe(16),
        }
    )


def consume_state(state: str, user: str, tool: str, arguments: dict) -> None:
    payload, remaining = _matching_payload(state, user, tool, arguments)
    _mark_nonce_used(payload["nonce"], remaining)


def input_required(question: str, verb: str, state: str) -> dict:
    return {
        "resultType": "input_required",
        "inputRequests": {
            INPUT_KEY: {
                "method": "elicitation/create",
                "params": {
                    "mode": "form",
                    "message": question,
                    "requestedSchema": {
                        "type": "object",
                        "properties": {INPUT_KEY: {"type": "boolean", "title": verb}},
                        "required": [INPUT_KEY],
                    },
                },
            }
        },
        "requestState": state,
    }


def accepted(input_responses: dict) -> bool:
    if not isinstance(input_responses, dict):
        return False
    response = input_responses.get(INPUT_KEY)
    if not isinstance(response, dict) or response.get("action") != "accept":
        return False
    content = response.get("content")
    return isinstance(content, dict) and content.get(INPUT_KEY) is True


def gate(tool_name: str, tool: dict, params: dict) -> Optional[dict]:
    """Decide whether this tools/call may run now.

    Returns the result to send instead of running (``input_required``, or the "did not confirm"
    error result), or None to run the tool. Only a modern-era client that declared form
    elicitation is asked; everyone else runs as before. Raises ``ProtocolError`` (-32602) when a
    ``requestState`` is invalid, expired, already used or for another call, so call it outside
    the tool's own error handling, which would turn that into a tool error.
    """
    question = _question(tool, params)
    if question is None:
        return None
    if request_is_from_fac_cloud():
        # FAC Chat shows its own approval card before calling, whatever AR declares.
        return None

    user = frappe.session.user
    arguments = params.get("arguments", {})
    state = params.get("requestState")
    if state is None:
        return _ask(question, tool, user, tool_name, arguments)

    try:
        responses = params.get("inputResponses")
        if not (isinstance(responses, dict) and isinstance(responses.get(INPUT_KEY), dict)):
            # MRTR: a verified state without an answer is asked again, with a fresh state.
            _matching_payload(state, user, tool_name, arguments)
            return _ask(question, tool, user, tool_name, arguments)
        consume_state(state, user, tool_name, arguments)
    except ConsentRefused as exc:
        frappe.logger().info(f"MCP confirmation refused for {tool_name}: {exc}")
        raise ProtocolError(
            400, ERR_INVALID_PARAMS, _("confirmation expired or does not match; call the tool again")
        ) from None

    if accepted(responses):
        return None
    return {
        "content": [{"type": "text", "text": _("The user did not confirm, so nothing was changed.")}],
        "isError": True,
    }


def _question(tool: dict, params: dict) -> Optional[str]:
    if getattr(frappe.local, "mcp_era", "handshake") != "modern":
        return None
    caps = getattr(frappe.local, "mcp_client_caps", None)
    if not getattr(caps, "elicitation_form", False):
        return None
    ask = tool.get("confirmation")
    return ask(params.get("arguments", {})) if callable(ask) else None


def _ask(question: str, tool: dict, user: str, tool_name: str, arguments) -> dict:
    verb = tool.get("confirmationVerb") or _("Confirm")
    return input_required(question, verb, issue_state(user, tool_name, arguments))


def _matching_payload(state, user: str, tool: str, arguments) -> tuple:
    """Verify ``state`` for this exact call without claiming it; return (payload, seconds left)."""
    payload = _verified_payload(state)

    remaining = payload["exp"] - _now_timestamp()
    if remaining <= 0:
        raise ConsentRefused("expired")
    if payload["user"] != user or payload["tool"] != tool:
        raise ConsentRefused("issued for another user or tool")
    if not hmac.compare_digest(payload["args_sha256"], _arguments_digest(arguments)):
        raise ConsentRefused("arguments changed")
    return payload, remaining


def _signing_key() -> bytes:
    return hmac.new(get_encryption_key().encode(), _KEY_LABEL, hashlib.sha256).digest()


def _mac(segment: bytes) -> bytes:
    return hmac.new(_signing_key(), segment, hashlib.sha256).digest()


def _sign(payload) -> str:
    segment = _b64encode(json.dumps(payload, separators=(",", ":")).encode())
    return f"{segment}.{_b64encode(_mac(segment.encode()))}"


def _verified_payload(state) -> dict:
    """Return the payload of a correctly signed, well-formed token; the MAC is checked first."""
    if not isinstance(state, str):
        raise ConsentRefused("not a string")
    parts = state.split(".")
    if len(parts) != 2:
        raise ConsentRefused("malformed")
    segment, mac = parts
    try:
        signature = _b64decode(mac)
        signed_bytes = segment.encode("ascii")
    except ValueError as exc:
        raise ConsentRefused("malformed") from exc
    if not hmac.compare_digest(signature, _mac(signed_bytes)):
        raise ConsentRefused("bad signature")

    try:
        payload = json.loads(_b64decode(segment))
    except ValueError as exc:
        raise ConsentRefused("malformed payload") from exc
    if not isinstance(payload, dict):
        raise ConsentRefused("malformed payload")
    for field, expected in _PAYLOAD_FIELDS.items():
        value = payload.get(field)
        if not isinstance(value, expected) or isinstance(value, bool):
            raise ConsentRefused("malformed payload")
    return payload


def _mark_nonce_used(nonce: str, remaining_seconds: int) -> None:
    """Atomically claim the nonce (SET NX), so two concurrent retries cannot both pass."""
    try:
        # nosemgrep: frappe-cache-breaks-multitenancy — the key is site-prefixed (make_key); set_value has no NX
        claimed = frappe.cache.set(
            frappe.cache.make_key(_nonce_key(nonce)),
            1,
            nx=True,
            ex=max(1, remaining_seconds),
        )
    except redis.exceptions.RedisError as exc:
        raise ConsentRefused("single-use store unavailable") from exc
    if not claimed:
        raise ConsentRefused("already used")


def _nonce_key(nonce: str) -> str:
    return _NONCE_CACHE_PREFIX + nonce


def _arguments_digest(arguments: dict) -> str:
    canonical = json.dumps(arguments, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


def _now_timestamp() -> int:
    return int(now_datetime().timestamp())


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64decode(text: str) -> bytes:
    """Strict base64url decode; raises ValueError (binascii.Error) on anything off-alphabet."""
    padded = text + "=" * (-len(text) % 4)
    return base64.b64decode(padded.encode("ascii"), altchars=b"-_", validate=True)
