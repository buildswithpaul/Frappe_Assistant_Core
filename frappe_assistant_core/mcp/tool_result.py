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
The one path every MCP tool result takes on its way to the client.

``unwrap_tool_result`` strips the ``_safe_execute`` envelope; ``finish_unwrapped`` does the
rest (vision image, fencing of untrusted fields, serialisation). ``finish_tool_result`` is both
in sequence, for a raw return value. A caller that already holds an unwrapped result, such as a
task completed after the call returned, uses ``finish_unwrapped`` so fencing stays in one place.
"""

import json
from typing import Any

from frappe_assistant_core.mcp.protocol import is_modern_era

_IMAGE_MIME_TYPES = {
    "jpeg": "image/jpeg",
    "jpg": "image/jpeg",
    "png": "image/png",
    "gif": "image/gif",
    "webp": "image/webp",
}


def unwrap_tool_result(tool: dict, raw: Any) -> tuple[Any, bool, bool]:
    """Return (result, is_error, own_message) with the ``_safe_execute`` envelope removed.

    own_message marks an error FAC wrote itself, with nothing of the user's file in it.
    """
    if not (tool.get("safeExecuteEnvelope") and isinstance(raw, dict)):
        return raw, False, False
    if raw.get("success") is True and "result" in raw:
        return raw["result"], False, False
    if raw.get("success") is False:
        inner = raw.get("result")
        result = (
            inner
            if isinstance(inner, dict)
            else {
                "success": False,
                "error": raw.get("error") or "Tool execution failed",
                "error_type": raw.get("error_type") or "ExecutionError",
            }
        )
        return result, True, bool(raw.get("own_message"))
    return raw, False, False


def finish_unwrapped(tool: dict, result: Any, is_error: bool = False, own_message: bool = False) -> dict:
    """Turn an unwrapped tool result into ``{"content": [...], "isError": bool}``, with
    ``structuredContent`` when the tool declares an output schema, the call succeeded and the
    client is in the modern era."""
    # Tools can include _image_content so the LLM sees the image via vision, not just metadata.
    image_content = None
    if isinstance(result, dict):
        image_content = result.pop("_image_content", None)

    # The user's file content, fenced so the model reads it as data (#34003).
    if isinstance(result, dict):
        from frappe_assistant_core.utils.untrusted_output import fence_fields, with_notice

        if tool.get("untrustedFields"):
            fenced = [f for f in tool["untrustedFields"] if not (own_message and f == "error")]
            result = fence_fields(result, fenced)
        # once per reply, for its fields and the records get_document fenced itself
        result = with_notice(result)

    # default=str handles datetime, Decimal, etc.
    result_text = (
        result
        if isinstance(result, str)
        else json.dumps(result, default=str, ensure_ascii=False, separators=(",", ":"))
    )
    content = [{"type": "text", "text": result_text}]

    if image_content and isinstance(image_content, dict):
        fmt = image_content.get("format", "jpeg")
        content.append(
            {
                "type": "image",
                "mimeType": _IMAGE_MIME_TYPES.get(fmt, f"image/{fmt}"),
                "data": image_content["data"],
            }
        )

    reply = {"content": content, "isError": is_error}
    # The same result as data, for a client that reads fields: taken from the text, so it is
    # fenced exactly as the text is. A failure is described by isError, not by the schema.
    # Modern era only: the only clients whose tools/list names an output schema.
    if tool.get("outputSchema") and isinstance(result, dict) and not is_error and is_modern_era():
        reply["structuredContent"] = json.loads(result_text, parse_constant=_no_json_value)
    return reply


def _no_json_value(_constant: str) -> None:
    """NaN and the infinities, which a report can compute, are not JSON: a strict client would
    refuse the whole response. Inside the text they are only characters; as data they become null."""
    return None


def finish_tool_result(tool: dict, raw: Any) -> dict:
    """Unwrap a raw tool return value and finish it."""
    return finish_unwrapped(tool, *unwrap_tool_result(tool, raw))
