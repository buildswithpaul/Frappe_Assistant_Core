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
Custom MCP Server Implementation

A streamlined MCP server that fixes serialization issues and provides
full control over the implementation. Based on the MCP specification
with Frappe-specific optimizations.

Key improvements over frappe-mcp:
- Proper JSON serialization with `default=str` (handles datetime, Decimal, etc.)
- No Pydantic dependency (simpler, faster)
- Full error tracebacks for debugging
- Optional Bearer token authentication
- Frappe-native integration
"""

import json
import traceback
from collections import OrderedDict
from typing import Any, Dict, Optional

from werkzeug.wrappers import Request, Response

from frappe_assistant_core.mcp import protocol, skills
from frappe_assistant_core.utils.mcp_caller import request_is_from_fac_cloud

# TEMPORARY: old tool names still accepted by tools/call, mapped to their new name.
# Resolved before the tool is looked up, so an old name gets exactly the new tool's
# registry entry: the same enabled/role-access filtering, category annotations and
# execution path. Aliases are never listed in tools/list.
# Remove "submit_document" in the release after the one that ships this rename to
# document_action, once clients have picked up the new name from tools/list.
TOOL_NAME_ALIASES = {"submit_document": "document_action"}

SERVER_VERSION = protocol.SERVER_VERSION


class MCPServer:
    """
    Lightweight MCP server for Frappe.

    This class implements the Model Context Protocol (MCP) specification
    for tool calling with StreamableHTTP transport.

    Example:
        ```python
        from frappe_assistant_core.mcp.server import MCPServer
        from frappe_assistant_core.mcp.tool_adapter import register_base_tool
        from frappe_assistant_core.plugins.core.tools.list_documents import DocumentList

        mcp = MCPServer("my-server")

        @mcp.register()
        def handle_mcp():
            # Import and register BaseTool instances
            register_base_tool(mcp, DocumentList())
        ```

    Note:
        Tools are implemented as BaseTool subclasses and registered using
        the tool_adapter. The @mcp.tool decorator pattern is not supported.
    """

    def __init__(self, name: str = "frappe-assistant-core"):
        """
        Initialize MCP server.

        Args:
            name: Server name for identification
        """
        self.name = name
        self._tool_registry = OrderedDict()
        self._entry_fn = None

    def register(
        self,
        allow_guest: bool = False,
        xss_safe: bool = True,
        methods: list = None,
    ):
        """
        Decorator to register MCP endpoint with Frappe.

        This creates a whitelisted Frappe endpoint that handles MCP requests.

        Args:
            allow_guest: If True, allows unauthenticated access
            xss_safe: If True, response will not be sanitized for XSS
            methods: List of allowed HTTP methods (default: ["POST"])

        Example:
            ```python
            @mcp.register()
            def handle_mcp():
                # Import tool modules here
                pass
            ```
        """
        import frappe

        if methods is None:
            methods = ["POST"]

        whitelister = frappe.whitelist(
            allow_guest=allow_guest,
            xss_safe=xss_safe,
            methods=methods,
        )

        def decorator(fn):
            if self._entry_fn is not None:
                raise Exception("Only one MCP endpoint allowed per MCPServer instance")

            self._entry_fn = fn

            def wrapper() -> Response:
                # Run user's function to perform auth checks and build the
                # per-request tool registry. The registry is returned to keep it
                # off any shared/global state, so concurrent requests stay
                # isolated (see issue #197).
                result = fn()

                # If fn() returned a Response (e.g., 401 auth failure), use that.
                if isinstance(result, Response):
                    return result

                # Otherwise fn() returns the per-request tool registry (a dict),
                # or None to fall back to the shared registry.
                tool_registry = result if isinstance(result, dict) else None

                # Handle MCP request
                request = frappe.request
                response = Response()
                return self.handle(request, response, tool_registry=tool_registry)

            return whitelister(wrapper)

        return decorator

    def handle(self, request: Request, response: Response, tool_registry: Optional[Dict] = None) -> Response:
        """
        Handle MCP request - main entry point.

        Processes JSON-RPC 2.0 requests according to MCP specification.

        Args:
            request: Werkzeug Request object
            response: Werkzeug Response object
            tool_registry: Per-request tool registry (name -> tool_dict). When
                provided, all tool routing for this request reads from it instead
                of the shared ``self._tool_registry``. This is what keeps
                concurrent requests isolated: each request builds its own
                registry on the call stack rather than mutating a process-global
                one. Falls back to ``self._tool_registry`` when not supplied
                (e.g. tools registered directly via ``add_tool``).

        Returns:
            Populated Response object with MCP response
        """
        import frappe

        # Per-request registry isolates concurrent requests. Never mutate the
        # shared singleton during request handling.
        if tool_registry is None:
            tool_registry = self._tool_registry

        # Set before any early return, so nothing from a previous request on this worker survives.
        protocol.set_request_state()

        # Only POST allowed
        if request.method != "POST":
            response.status_code = 405
            return response

        # Parse JSON request
        try:
            data = request.get_json(force=True)
            # Log incoming request for debugging
            frappe.logger().debug(f"MCP Request: method={data.get('method')}, id={data.get('id')}")
        except Exception as e:
            frappe.logger().error(
                f"MCP Parse Error: {str(e)}, Raw data: {request.get_data(as_text=True)[:500]}"
            )
            return self._error_response(response, None, -32700, f"Parse error: {str(e)}")

        # Check if notification (no response needed)
        if self._is_notification(data):
            response.status_code = 202  # Accepted
            # Echo MCP-Protocol-Version header if present (2025-06-18 spec)
            incoming_version = frappe.request.headers.get("mcp-protocol-version")
            if incoming_version:
                response.headers["mcp-protocol-version"] = incoming_version
            return response

        # Get request ID
        request_id = data.get("id")
        if request_id is None:
            return self._error_response(response, None, -32600, "Invalid Request: missing id")

        try:
            era, caps = protocol.resolve_request(request.headers, data)
        except protocol.ProtocolError as e:
            return self._error_response(
                response, request_id, e.code, e.message, http_status=e.http_status, data=e.data
            )
        protocol.set_request_state(era, caps)
        self._populate_correlation_ids(request, data, era)

        method = data.get("method")
        params = data.get("params", {})

        try:
            if method == "initialize":
                result = self._handle_initialize(params)
            elif method == "tools/list":
                result = self._handle_tools_list(params, tool_registry)
            elif method == "tools/call":
                call_arguments = params.get("arguments", {})
                argument_keys = sorted(call_arguments) if isinstance(call_arguments, dict) else []
                frappe.logger().info(
                    f"MCP tools/call: tool={params.get('name')}, argument_keys={argument_keys}"
                )
                result = self._handle_tools_call(params, tool_registry)
            elif method == "resources/list":
                result = self._handle_resources_list(params, request_id)
            elif method == "resources/read":
                result = self._handle_resources_read(params, request_id)
            elif era == "modern" and method in skills.MODERN_METHODS:
                result = skills.MODERN_METHODS[method](params)
            elif method == "resources/templates/list":
                result = {"resourceTemplates": []}
            elif method == "prompts/list":
                result = self._handle_prompts_list(params, request_id)
            elif method == "prompts/get":
                result = self._handle_prompts_get(params, request_id)
            elif method == "ping" and era == "handshake":
                result = {}
            elif method == "server/discover" and era == "modern":
                result = protocol.discover_result(server_name=self.name, server_version=SERVER_VERSION)
            else:
                frappe.logger().warning(f"MCP Unknown method: {method}")
                status = 404 if era == "modern" else 400
                return self._error_response(
                    response, request_id, -32601, f"Method not found: {method}", status
                )
        except protocol.ProtocolError as e:
            return self._error_response(
                response, request_id, e.code, e.message, http_status=e.http_status, data=e.data
            )
        except Exception as e:
            frappe.logger().error(
                f"MCP Handler Error for method '{method}': {str(e)}\n{traceback.format_exc()}"
            )
            return self._error_response(response, request_id, -32603, f"Internal error: {str(e)}")

        result = protocol.finish_result(era, method, result, self.name, SERVER_VERSION)

        return self._success_response(response, request_id, result)

    def add_tool(self, tool_dict: Dict):
        """
        Programmatically add a tool.

        Used by tool_adapter to register BaseTool instances.

        Args:
            tool_dict: Dict with keys: name, description, inputSchema, fn, annotations
        """
        self._tool_registry[tool_dict["name"]] = tool_dict

    def _populate_correlation_ids(self, request: Request, data: Dict, era: str):
        """Tag audit logs with the caller's session and client (see protocol.session_id)."""
        import frappe

        frappe.local.assistant_session_id = protocol.session_id(request.headers, era)
        frappe.local.assistant_client_id = protocol.declared_client_name(request.headers, data)

    def _handle_initialize(self, params: Dict) -> Dict:
        """
        Handle initialize request.

        Declares server capabilities according to MCP 2025-06-18 spec.
        We only support tools (not prompts, resources, or sampling).
        """
        import frappe

        # Get protocol version from settings
        protocol_version = "2025-06-18"  # Default
        try:
            settings = frappe.get_single("Assistant Core Settings")
            protocol_version = settings.mcp_protocol_version or protocol_version
        except Exception:
            pass

        return {
            "protocolVersion": protocol_version,
            "capabilities": {
                "tools": {},  # We support tools
                "prompts": {},  # We support prompts (database-driven templates)
                "resources": {},  # We support resources (skill documents)
            },
            "serverInfo": {"name": self.name, "version": SERVER_VERSION},
        }

    def _handle_tools_list(self, params: Dict, tool_registry: Optional[Dict] = None) -> Dict:
        """Handle tools/list request with optional token optimization."""
        import frappe

        if tool_registry is None:
            tool_registry = self._tool_registry

        tools_list = []

        # Replace mode is for FAC Chat, which loads the skill through get_skill; other clients keep full text.
        skill_replace_map = {}
        try:
            settings = frappe.get_single("Assistant Core Settings")
            if getattr(settings, "skill_mode", "supplementary") == "replace" and request_is_from_fac_cloud():
                from frappe_assistant_core.api.handlers.resources import get_skill_manager

                skill_replace_map = get_skill_manager().get_tool_skill_map(user=frappe.session.user)
        except Exception:
            pass

        packs, pack_of = self._tool_packs()

        for tool in tool_registry.values():
            description = tool["description"]

            # In replace mode, minimize descriptions for tools with linked skills
            if skill_replace_map and tool["name"] in skill_replace_map:
                skill_info = skill_replace_map[tool["name"]]
                description = f"{tool['name']}: {skill_info['description']}. Detailed guidance: fac://skills/{skill_info['skill_id']}"

            tool_spec = {
                "name": tool["name"],
                "description": description,
                "inputSchema": tool["inputSchema"],
            }

            # Add annotations if present
            if tool.get("annotations"):
                tool_spec["annotations"] = tool["annotations"]

            if tool["name"] in pack_of:
                tool_spec["_meta"] = {"fac/pack": pack_of[tool["name"]]}

            tools_list.append(tool_spec)

        result = {"tools": tools_list}

        # Only AR reads the catalogue; other MCP clients get the listing unchanged.
        ar_session_id = getattr(frappe.local, "ar_session_id", None)
        if ar_session_id and packs is not None:
            listing_meta = self._tool_pack_meta(packs, [t["name"] for t in tools_list], ar_session_id)
            if listing_meta is not None:
                result["_meta"] = listing_meta

        return result

    @staticmethod
    def _tool_packs() -> tuple:
        """The enabled plugins' tool packs and ``{tool: pack_id}``; ``(None, {})`` when they can't
        be read, and every tool is then listed as base."""
        import frappe

        from frappe_assistant_core.core import tool_pack_listing
        from frappe_assistant_core.utils.plugin_manager import get_plugin_manager

        try:
            packs = get_plugin_manager().get_tool_packs()
            return packs, tool_pack_listing.pack_map(packs)
        except Exception:
            frappe.logger().warning(
                "MCP tools/list: tool packs unreadable, listing every tool as base", exc_info=True
            )
            return None, {}

    @staticmethod
    def _tool_pack_meta(packs: list, listed: list, ar_session_id: str) -> Optional[Dict]:
        """The listing ``_meta`` AR reads: the pack catalogue, the packs this conversation's
        files want and the user's tool-loading choice. None when it can't be built: tools/list must never fail for it."""
        import frappe

        from frappe_assistant_core.core import tool_pack_listing

        try:
            meta = {
                "fac/packs": tool_pack_listing.catalogue(packs, listed),
                "fac/wanted_packs": tool_pack_listing.wanted_packs(ar_session_id, frappe.session.user, packs),
            }
        except Exception:
            frappe.logger().warning(
                "MCP tools/list: tool pack catalogue unreadable, sent without it", exc_info=True
            )
            return None
        meta.update(MCPServer._tool_loading_meta())
        return meta

    @staticmethod
    def _tool_loading_meta() -> Dict:
        """``{"fac/tool_loading": "dynamic" | "all"}`` for the session user; empty when the
        preference can't be read, which AR treats as dynamic."""
        import frappe

        from frappe_assistant_core.chat.tool_loading import tool_loading_mode

        try:
            return {"fac/tool_loading": tool_loading_mode(frappe.session.user)}
        except Exception:
            frappe.logger().warning("MCP tools/list: tool loading preference unreadable", exc_info=True)
            return {}

    def _handle_tools_call(self, params: Dict, tool_registry: Optional[Dict] = None) -> Dict:
        """
        Handle tools/call request.

        This is the CRITICAL method that fixes the serialization issue.
        Uses json.dumps with default=str to handle datetime, Decimal, etc.
        """
        import frappe

        if tool_registry is None:
            tool_registry = self._tool_registry

        tool_name = params.get("name")
        arguments = params.get("arguments", {})

        # Before any check sees the name, so an old name can't be treated differently.
        if tool_name in TOOL_NAME_ALIASES:
            frappe.logger().info(
                f"MCP tool alias used: {tool_name} -> {TOOL_NAME_ALIASES[tool_name]} (deprecated name)"
            )
            tool_name = TOOL_NAME_ALIASES[tool_name]

        argument_keys = sorted(arguments) if isinstance(arguments, dict) else []
        frappe.logger().debug(f"MCP _handle_tools_call: tool={tool_name}, argument_keys={argument_keys}")

        # Check tool exists
        if tool_name not in tool_registry:
            error_msg = f"Tool '{tool_name}' not found or not available for the current user."
            # The full list stays in the log rather than the model-facing error, which
            # would otherwise repeat every tool name on each miss.
            frappe.logger().error(f"MCP Tool Not Found: {error_msg} Available: {sorted(tool_registry)}")
            return {
                "content": [{"type": "text", "text": error_msg}],
                "isError": True,
            }

        tool = tool_registry[tool_name]
        fn = tool["fn"]

        try:
            # Execute tool
            frappe.logger().info(f"MCP Executing tool: {tool_name}")
            result = fn(**arguments)
            frappe.logger().info(
                f"MCP Tool {tool_name} executed successfully, result type: {type(result).__name__}"
            )

            is_error = False
            own_message = False  # an error FAC wrote itself, with nothing of the user's file in it
            if tool.get("safeExecuteEnvelope") and isinstance(result, dict):
                if result.get("success") is True and "result" in result:
                    result = result["result"]
                elif result.get("success") is False:
                    is_error = True
                    inner = result.get("result")
                    own_message = bool(result.get("own_message"))
                    result = (
                        inner
                        if isinstance(inner, dict)
                        else {
                            "success": False,
                            "error": result.get("error") or "Tool execution failed",
                            "error_type": result.get("error_type") or "ExecutionError",
                        }
                    )

            # Extract image content for vision API (e.g., screenshot tool).
            # Tools can include _image_content in their result to have the LLM
            # see the image directly via vision, rather than just getting metadata.
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

            # Serialize the text result (default=str handles datetime, Decimal, etc.)
            if isinstance(result, str):
                result_text = result
            else:
                result_text = json.dumps(
                    result,
                    default=str,
                    ensure_ascii=False,
                    separators=(",", ":"),
                )

            # Build MCP content blocks
            content = [{"type": "text", "text": result_text}]

            # Add image block for vision API if tool provided one
            if image_content and isinstance(image_content, dict):
                mime_map = {
                    "jpeg": "image/jpeg",
                    "jpg": "image/jpeg",
                    "png": "image/png",
                    "gif": "image/gif",
                    "webp": "image/webp",
                }
                fmt = image_content.get("format", "jpeg")
                content.append(
                    {
                        "type": "image",
                        "mimeType": mime_map.get(fmt, f"image/{fmt}"),
                        "data": image_content["data"],
                    }
                )

            return {"content": content, "isError": is_error}

        except Exception as e:
            error_text = f"Error executing {tool_name}: {str(e)}"
            frappe.logger().error(f"MCP Tool Execution Error: {error_text}\n{traceback.format_exc()}")

            return {"content": [{"type": "text", "text": error_text}], "isError": True}

    def _success_response(self, response: Response, request_id: Any, result: Dict) -> Response:
        """Create JSON-RPC success response."""
        import frappe

        response_data = {"jsonrpc": "2.0", "id": request_id, "result": result}

        # Use default=str here too for consistency
        response.data = json.dumps(response_data, default=str)
        response.mimetype = "application/json"
        response.status_code = 200

        # Echo MCP-Protocol-Version header if present (2025-06-18 spec)
        incoming_version = frappe.request.headers.get("mcp-protocol-version")
        if incoming_version:
            response.headers["mcp-protocol-version"] = incoming_version

        return response

    def _error_response(
        self,
        response: Response,
        request_id: Optional[Any],
        code: int,
        message: str,
        http_status: int = 400,
        data: Optional[Dict] = None,
    ) -> Response:
        """Create JSON-RPC error response."""
        import frappe

        error = {"code": code, "message": message}
        if data is not None:
            error["data"] = data
        response_data = {"jsonrpc": "2.0", "id": request_id, "error": error}

        response.data = json.dumps(response_data)
        response.mimetype = "application/json"
        response.status_code = http_status

        # Echo MCP-Protocol-Version header if present (2025-06-18 spec)
        incoming_version = frappe.request.headers.get("mcp-protocol-version")
        if incoming_version:
            response.headers["mcp-protocol-version"] = incoming_version

        return response

    def _handle_prompts_list(self, params: Dict, request_id: Any) -> Dict:
        """
        Handle prompts/list request.

        Returns available prompt templates from the database.
        """
        from frappe_assistant_core.api.handlers.prompts import handle_prompts_list

        # The handler returns a full JSON-RPC response, extract just the result
        response = handle_prompts_list(request_id)
        if "result" in response:
            return response["result"]
        # If there's an error, return empty prompts list
        return {"prompts": []}

    def _handle_prompts_get(self, params: Dict, request_id: Any) -> Dict:
        """
        Handle prompts/get request.

        Returns a specific prompt template rendered with provided arguments.
        """
        from frappe_assistant_core.api.handlers.prompts import handle_prompts_get

        # The handler returns a full JSON-RPC response, extract just the result
        response = handle_prompts_get(params, request_id)
        if "result" in response:
            return response["result"]
        # If there's an error, re-raise it
        if "error" in response:
            raise Exception(response["error"].get("message", "Unknown prompt error"))
        return {}

    def _handle_resources_list(self, params: Dict, request_id: Any) -> Dict:
        """
        Handle resources/list request.

        Returns available skill documents as MCP resources.
        """
        from frappe_assistant_core.api.handlers.resources import handle_resources_list

        return handle_resources_list(request_id)

    def _handle_resources_read(self, params: Dict, request_id: Any) -> Dict:
        """Handle resources/read: the content of one skill resource by URI."""
        from frappe_assistant_core.api.handlers.resources import handle_resources_read

        return skills.read_resource(params, lambda p: handle_resources_read(p, request_id))

    def _is_notification(self, data: Dict) -> bool:
        """Check if request is a notification (no response needed)."""
        method = data.get("method", "")
        return isinstance(method, str) and method.startswith("notifications/")
