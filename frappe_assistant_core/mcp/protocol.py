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
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""
Pure MCP protocol rules: era routing, modern-era header validation, client capability parsing
and result decoration. No I/O, so it is unit-testable without a request.
"""

import base64
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

from frappe import _

HANDSHAKE_VERSIONS: tuple[str, ...] = ("2024-11-05", "2025-03-26", "2025-06-18")
MODERN_VERSIONS: tuple[str, ...] = ("2026-07-28",)
ALL_VERSIONS: tuple[str, ...] = HANDSHAKE_VERSIONS + MODERN_VERSIONS

SKILLS_EXT = "io.modelcontextprotocol/skills"
TASKS_EXT = "io.modelcontextprotocol/tasks"

META_VERSION = "io.modelcontextprotocol/protocolVersion"
META_CAPABILITIES = "io.modelcontextprotocol/clientCapabilities"
META_SERVER_INFO = "io.modelcontextprotocol/serverInfo"
META_CLIENT_INFO = "io.modelcontextprotocol/clientInfo"

SERVER_VERSION = "2.0.0"

LIST_TTL_MS = 300_000
READ_TTL_MS = 60_000
# Results a client may cache, and for how long. The tool list depends on the caller's roles, so
# the scope is always "private".
_TTL_MS = {
    "tools/list": LIST_TTL_MS,
    "prompts/list": LIST_TTL_MS,
    "resources/list": LIST_TTL_MS,
    "resources/templates/list": LIST_TTL_MS,
    "resources/read": READ_TTL_MS,
}

ERR_HEADER_MISMATCH = -32020
ERR_UNSUPPORTED_VERSION = -32022
ERR_INVALID_PARAMS = -32602

# Methods whose Mcp-Name header must equal a params field.
_NAME_FIELD = {"tools/call": "name", "prompts/get": "name", "resources/read": "uri"}
_BASE64_SENTINEL = re.compile(r"^=\?base64\?(.*)\?=$", re.DOTALL)


class ProtocolError(Exception):
    """A protocol violation that maps to an HTTP status and a JSON-RPC error."""

    def __init__(self, http_status: int, code: int, message: str, data: dict | None = None):
        super().__init__(message)
        self.http_status = http_status
        self.code = code
        self.message = message
        self.data = data


@dataclass(frozen=True)
class ClientCaps:
    elicitation_form: bool = False
    tasks: bool = False


def era_of(method: str, header_version: str | None) -> Literal["handshake", "modern"]:
    if method == "initialize" or not header_version:
        return "handshake"
    if header_version in MODERN_VERSIONS:
        return "modern"
    if header_version in HANDSHAKE_VERSIONS:
        return "handshake"
    raise ProtocolError(
        400,
        ERR_UNSUPPORTED_VERSION,
        _("Unsupported protocol version"),
        {"supported": list(ALL_VERSIONS), "requested": header_version},
    )


def _header(headers: Mapping[str, str], name: str) -> str | None:
    wanted = name.lower()
    for key, value in headers.items():
        if key.lower() == wanted:
            return value
    return None


def _decode_header_value(value: str) -> str:
    match = _BASE64_SENTINEL.match(value)
    if not match:
        return value
    try:
        return base64.b64decode(match.group(1), validate=True).decode("utf-8")
    except ValueError:
        raise ProtocolError(400, ERR_HEADER_MISMATCH, _("Malformed base64 header value")) from None


def _meta(body: dict) -> dict:
    params = body.get("params")
    meta = params.get("_meta") if isinstance(params, dict) else None
    return meta if isinstance(meta, dict) else {}


def validate_modern_request(headers: Mapping[str, str], body: dict) -> None:
    if not isinstance(body.get("params", {}), dict):
        raise ProtocolError(400, ERR_INVALID_PARAMS, _("params must be an object"))
    meta = _meta(body)
    if meta.get(META_VERSION) != _header(headers, "MCP-Protocol-Version"):
        raise ProtocolError(
            400, ERR_HEADER_MISMATCH, _("_meta protocolVersion must match the MCP-Protocol-Version header")
        )
    if not isinstance(meta.get(META_CAPABILITIES), dict):
        raise ProtocolError(400, ERR_INVALID_PARAMS, _("_meta clientCapabilities is required"))

    method = body.get("method")
    mcp_method = _header(headers, "Mcp-Method")
    if mcp_method is None or _decode_header_value(mcp_method) != method:
        raise ProtocolError(400, ERR_HEADER_MISMATCH, _("Mcp-Method header must match the request method"))

    field = _NAME_FIELD.get(method)
    if field:
        mcp_name = _header(headers, "Mcp-Name")
        expected = (body.get("params") or {}).get(field)
        if mcp_name is None or _decode_header_value(mcp_name) != expected:
            raise ProtocolError(
                400, ERR_HEADER_MISMATCH, _("Mcp-Name header must match the request {0}").format(field)
            )


def client_caps(body: dict) -> ClientCaps:
    caps = _meta(body).get(META_CAPABILITIES)
    if not isinstance(caps, dict):
        return ClientCaps()
    elicitation = caps.get("elicitation")
    extensions = caps.get("extensions")
    return ClientCaps(
        elicitation_form=isinstance(elicitation, dict) and (not elicitation or "form" in elicitation),
        tasks=isinstance(extensions, dict) and TASKS_EXT in extensions,
    )


def set_request_state(era: str = "handshake", caps: ClientCaps | None = None) -> None:
    """Publish the request's era and capabilities on frappe.local, for tools to read."""
    import frappe

    frappe.local.mcp_era = era
    frappe.local.mcp_client_caps = caps or ClientCaps()


def resolve_request(headers: Mapping[str, str], body: dict) -> tuple[str, ClientCaps]:
    """Decide a request's era and, in the modern era, check its headers and read its capabilities.

    Raises ProtocolError for an unknown version or a malformed modern request.
    """
    era = era_of(body.get("method"), _header(headers, "MCP-Protocol-Version"))
    if era == "handshake":
        return era, ClientCaps()
    validate_modern_request(headers, body)
    return era, client_caps(body)


def session_id(headers: Mapping[str, str], era: str) -> str | None:
    """The caller's own session id, or None. Nothing is minted: a random id groups nothing.

    The modern era has no Mcp-Session-Id; FAC Chat names its conversation in X-AR-Session-Id.
    """
    names = ["X-Assistant-Session-Id"]
    names = ["X-AR-Session-Id"] + names if era == "modern" else ["Mcp-Session-Id"] + names
    return next((value for value in (_header(headers, name) for name in names) if value), None)


def declared_client_name(headers: Mapping[str, str], body: dict) -> str | None:
    """The client's name: the explicit header, else ``clientInfo`` from initialize params or, in the
    modern era, from every request's ``_meta``."""
    explicit = _header(headers, "X-Assistant-Client-Id")
    if explicit:
        return explicit
    params = body.get("params")
    if not isinstance(params, dict):
        return None
    for info in (params.get("clientInfo"), _meta(body).get(META_CLIENT_INFO)):
        if isinstance(info, dict) and info.get("name"):
            return info["name"]
    return None


def _server_info(server_name: str, server_version: str) -> dict:
    return {"name": server_name, "version": server_version}


def finish_result(era: str, method: str, result: dict, server_name: str, server_version: str) -> dict:
    """Decorate a modern-era result; a handshake-era result is returned untouched."""
    if era != "modern":
        return result
    ttl_ms = _TTL_MS.get(method)
    return decorate_result(
        result,
        server_name=server_name,
        server_version=server_version,
        cache=ttl_ms is not None,
        ttl_ms=ttl_ms,
    )


def decorate_result(
    result: dict, *, server_name: str, server_version: str, cache: bool, ttl_ms: int | None
) -> dict:
    result.setdefault("resultType", "complete")
    result.setdefault("_meta", {})[META_SERVER_INFO] = _server_info(server_name, server_version)
    if cache:
        result["ttlMs"] = ttl_ms
        result["cacheScope"] = "private"
    return result


def discover_result(*, server_name: str, server_version: str) -> dict:
    return {
        "resultType": "complete",
        "supportedVersions": list(ALL_VERSIONS),
        "capabilities": {
            "tools": {},
            "prompts": {},
            "resources": {},
            "extensions": {SKILLS_EXT: {}, TASKS_EXT: {}},
        },
        "_meta": {META_SERVER_INFO: _server_info(server_name, server_version)},
        "ttlMs": LIST_TTL_MS,
        "cacheScope": "private",
    }
