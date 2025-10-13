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
from inspect import Parameter, getdoc, signature
from typing import Any, Callable, Dict, Optional

from werkzeug.wrappers import Request, Response


class MCPServer:
    """
    Lightweight MCP server for Frappe.

    This class implements the Model Context Protocol (MCP) specification
    for tool calling with StreamableHTTP transport.

    Example:
        ```python
        from frappe_assistant_core.mcp.server import MCPServer

        mcp = MCPServer("my-server")

        @mcp.tool(description="Get weather")
        def get_weather(location: str):
            return {"temperature": 72, "location": location}

        @mcp.register()
        def handle_mcp():
            pass  # Import tools here
        ```
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
                # Run user's function to import tools and perform auth checks
                result = fn()

                # If fn() returned a response (e.g., 401 auth failure), use that
                if result is not None:
                    return result

                # Handle MCP request
                request = frappe.request
                response = Response()
                return self.handle(request, response)

            return whitelister(wrapper)

        return decorator

    def handle(self, request: Request, response: Response) -> Response:
        """
        Handle MCP request - main entry point.

        Processes JSON-RPC 2.0 requests according to MCP specification.

        Args:
            request: Werkzeug Request object
            response: Werkzeug Response object

        Returns:
            Populated Response object with MCP response
        """
        import frappe

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
            return response

        # Get request ID
        request_id = data.get("id")
        if request_id is None:
            return self._error_response(response, None, -32600, "Invalid Request: missing id")

        # Route method
        method = data.get("method")
        params = data.get("params", {})

        result = None

        try:
            if method == "initialize":
                result = self._handle_initialize(params)
            elif method == "tools/list":
                result = self._handle_tools_list(params)
            elif method == "tools/call":
                frappe.logger().info(
                    f"MCP tools/call: tool={params.get('name')}, args={json.dumps(params.get('arguments', {}), default=str)[:200]}"
                )
                result = self._handle_tools_call(params)
            elif method == "resources/list":
                # Return empty resources list (we don't support resources)
                result = {"resources": []}
            elif method == "prompts/list":
                # Return empty prompts list (we don't support prompts)
                result = {"prompts": []}
            elif method == "ping":
                result = {}
            else:
                frappe.logger().warning(f"MCP Unknown method: {method}")
                return self._error_response(response, request_id, -32601, f"Method not found: {method}")
        except Exception as e:
            # Log unexpected errors
            frappe.logger().error(
                f"MCP Handler Error for method '{method}': {str(e)}\n{traceback.format_exc()}"
            )
            return self._error_response(response, request_id, -32603, f"Internal error: {str(e)}")

        # Success response
        return self._success_response(response, request_id, result)

    def tool(
        self,
        description: str = None,
        name: str = None,
        input_schema: Dict = None,
        **annotations,
    ):
        """
        Decorator to register a tool.

        Args:
            description: Tool description (uses docstring if not provided)
            name: Tool name (uses function name if not provided)
            input_schema: JSON schema for inputs (auto-generated if not provided)
            **annotations: Additional tool annotations (readOnlyHint, etc.)

        Example:
            ```python
            @mcp.tool(description="List documents", readOnlyHint=True)
            def list_documents(doctype: str, limit: int = 20):
                return frappe.get_all(doctype, limit=limit)
            ```
        """

        def decorator(fn: Callable):
            tool_name = name or fn.__name__
            tool_desc = description or getdoc(fn) or ""

            # Generate input schema from function signature if not provided
            if input_schema is None:
                schema = self._generate_input_schema(fn)
            else:
                schema = input_schema

            # Register tool
            self._tool_registry[tool_name] = {
                "name": tool_name,
                "description": tool_desc,
                "inputSchema": schema,
                "annotations": annotations if annotations else None,
                "fn": fn,
            }

            return fn

        return decorator

    def add_tool(self, tool_dict: Dict):
        """
        Programmatically add a tool.

        Args:
            tool_dict: Dict with keys: name, description, inputSchema, fn, annotations
        """
        self._tool_registry[tool_dict["name"]] = tool_dict

    def _generate_input_schema(self, fn: Callable) -> Dict:
        """Generate JSON schema from function signature."""
        sig = signature(fn)
        properties = {}
        required = []

        for param_name, param in sig.parameters.items():
            # Get type from annotation
            param_type = self._get_json_type(param.annotation)

            properties[param_name] = {"type": param_type}

            # Check if required (no default value)
            if param.default == Parameter.empty:
                required.append(param_name)

        return {"type": "object", "properties": properties, "required": required}

    def _get_json_type(self, annotation) -> str:
        """Convert Python type to JSON schema type."""
        if annotation == Parameter.empty:
            return "string"

        type_map = {
            str: "string",
            int: "integer",
            float: "number",
            bool: "boolean",
            dict: "object",
            list: "array",
            Dict: "object",
        }

        # Handle string annotations
        if isinstance(annotation, str):
            lower_ann = annotation.lower()
            if "str" in lower_ann:
                return "string"
            if "int" in lower_ann:
                return "integer"
            if "float" in lower_ann or "number" in lower_ann:
                return "number"
            if "bool" in lower_ann:
                return "boolean"
            if "dict" in lower_ann or "object" in lower_ann:
                return "object"
            if "list" in lower_ann or "array" in lower_ann:
                return "array"

        return type_map.get(annotation, "string")

    def _handle_initialize(self, params: Dict) -> Dict:
        """
        Handle initialize request.

        Declares server capabilities according to MCP 2025-03-26 spec.
        We only support tools (not prompts, resources, or sampling).
        """
        import frappe

        # Get protocol version from settings
        protocol_version = "2025-03-26"  # Default
        try:
            settings = frappe.get_single("Assistant Core Settings")
            protocol_version = settings.mcp_protocol_version or protocol_version
        except Exception:
            pass

        return {
            "protocolVersion": protocol_version,
            "capabilities": {
                "tools": {},  # We support tools
                # Note: We respond to resources/list and prompts/list with empty arrays
                # but don't declare them as capabilities since we don't support them
            },
            "serverInfo": {"name": self.name, "version": "2.0.0"},
        }

    def _handle_tools_list(self, params: Dict) -> Dict:
        """Handle tools/list request."""
        tools_list = []

        for tool in self._tool_registry.values():
            tool_spec = {
                "name": tool["name"],
                "description": tool["description"],
                "inputSchema": tool["inputSchema"],
            }

            # Add annotations if present
            if tool.get("annotations"):
                tool_spec["annotations"] = tool["annotations"]

            tools_list.append(tool_spec)

        return {"tools": tools_list}

    def _handle_tools_call(self, params: Dict) -> Dict:
        """
        Handle tools/call request.

        This is the CRITICAL method that fixes the serialization issue.
        """
        import frappe

        tool_name = params.get("name")
        arguments = params.get("arguments", {})

        frappe.logger().debug(f"MCP _handle_tools_call: tool={tool_name}, args={arguments}")

        # Check tool exists
        if tool_name not in self._tool_registry:
            error_msg = f"Tool '{tool_name}' not found. Available tools: {list(self._tool_registry.keys())}"
            frappe.logger().error(f"MCP Tool Not Found: {error_msg}")
            return {
                "content": [{"type": "text", "text": error_msg}],
                "isError": True,
            }

        tool = self._tool_registry[tool_name]
        fn = tool["fn"]

        try:
            # Execute tool
            frappe.logger().info(f"MCP Executing tool: {tool_name}")
            result = fn(**arguments)
            frappe.logger().info(
                f"MCP Tool {tool_name} executed successfully, result type: {type(result).__name__}"
            )

            # CRITICAL FIX: Use json.dumps with default=str
            # This handles datetime, Decimal, and all other non-JSON types!
            if isinstance(result, str):
                result_text = result
            else:
                # The key fix: default=str converts any type to string
                result_text = json.dumps(result, default=str, indent=2)

            return {"content": [{"type": "text", "text": result_text}], "isError": False}

        except Exception as e:
            # Full traceback for debugging
            error_text = f"Error executing {tool_name}: {str(e)}\n\nTraceback:\n{traceback.format_exc()}"
            frappe.logger().error(f"MCP Tool Execution Error: {error_text}")

            return {"content": [{"type": "text", "text": error_text}], "isError": True}

    def _success_response(self, response: Response, request_id: Any, result: Dict) -> Response:
        """Create JSON-RPC success response."""
        response_data = {"jsonrpc": "2.0", "id": request_id, "result": result}

        # Use default=str here too for consistency
        response.data = json.dumps(response_data, default=str)
        response.mimetype = "application/json"
        response.status_code = 200
        return response

    def _error_response(
        self, response: Response, request_id: Optional[Any], code: int, message: str
    ) -> Response:
        """Create JSON-RPC error response."""
        response_data = {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}

        response.data = json.dumps(response_data)
        response.mimetype = "application/json"
        response.status_code = 400
        return response

    def _is_notification(self, data: Dict) -> bool:
        """Check if request is a notification (no response needed)."""
        method = data.get("method", "")
        return isinstance(method, str) and method.startswith("notifications/")
