# -*- coding: utf-8 -*-
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
MCP (Model Context Protocol) API endpoints for Frappe Assistant Core.
Handles communication between AI assistants and Frappe system.
"""

import frappe
from frappe import _
import json
import traceback
from typing import Dict, Any, List
from frappe_assistant_core.core.tool_registry import get_tool_registry
from frappe_assistant_core.utils.validators import validate_json_rpc


@frappe.whitelist(allow_guest=False)
def handle_mcp_request(request_data: str) -> str:
    """
    Main MCP request handler.
    
    Processes JSON-RPC 2.0 requests according to MCP specification.
    
    Args:
        request_data: JSON-RPC 2.0 request string
        
    Returns:
        JSON-RPC 2.0 response string
    """
    try:
        # Parse JSON request
        try:
            request = json.loads(request_data)
        except json.JSONDecodeError as e:
            return _create_error_response(
                None,
                -32700,
                "Parse error",
                f"Invalid JSON: {str(e)}"
            )
        
        # Validate JSON-RPC structure
        validation_error = validate_json_rpc(request)
        if validation_error:
            return _create_error_response(
                request.get("id"),
                -32600,
                "Invalid Request",
                validation_error
            )
        
        # Route to appropriate handler
        method = request.get("method")
        params = request.get("params", {})
        request_id = request.get("id")
        
        if method == "initialize":
            result = _handle_initialize(params)
        elif method == "tools/list":
            result = _handle_tools_list(params)
        elif method == "tools/call":
            result = _handle_tools_call(params)
        elif method == "ping":
            result = _handle_ping(params)
        else:
            return _create_error_response(
                request_id,
                -32601,
                "Method not found",
                f"Unknown method: {method}"
            )
        
        # Return success response
        return _create_success_response(request_id, result)
        
    except frappe.PermissionError as e:
        return _create_error_response(
            request.get("id") if "request" in locals() else None,
            -32603,
            "Permission denied",
            str(e)
        )
    except Exception as e:
        frappe.log_error(
            title=_("MCP Request Error"),
            message=f"Error processing MCP request: {str(e)}\\n{traceback.format_exc()}"
        )
        
        return _create_error_response(
            request.get("id") if "request" in locals() else None,
            -32603,
            "Internal error",
            "An internal error occurred"
        )


def get_app_version(app_name: str) -> str:
    """
    Get version of a Frappe app.
    
    Args:
        app_name: Name of the app
        
    Returns:
        Version string or empty string if not found
    """
    try:
        if app_name == "frappe_assistant_core":
            from frappe_assistant_core import __version__
            return __version__
        else:
            # For other apps, try to import and get __version__
            module = __import__(app_name)
            version = getattr(module, "__version__", None)
            return version if version else ""
    except ImportError:
        return ""


def _handle_initialize(params: Dict[str, Any]) -> Dict[str, Any]:
    """Handle MCP initialize request"""
    # Check protocol version
    protocol_version = params.get("protocolVersion", "")
    if not protocol_version:
        raise ValueError("Protocol version is required")
    
    # Return server capabilities
    return {
        "protocolVersion": "2025-06-18",
        "capabilities": {
            "tools": {
                "listChanged": True
            }
        },
        "serverInfo": {
            "name": "frappe-assistant-core",
            "version": get_app_version("frappe_assistant_core") or "1.0.0"
        }
    }


def _handle_tools_list(params: Dict[str, Any]) -> Dict[str, Any]:
    """Handle MCP tools/list request"""
    try:
        # Get tool registry
        registry = get_tool_registry()
        
        # Get available tools for current user
        tools = registry.get_available_tools()
        
        # Convert to MCP format
        mcp_tools = []
        for tool in tools:
            try:
                mcp_tool = tool.to_mcp_format()
                mcp_tools.append(mcp_tool)
            except Exception as e:
                frappe.logger("mcp").warning(f"Failed to convert tool {tool.name} to MCP format: {str(e)}")
        
        return {"tools": mcp_tools}
        
    except Exception as e:
        frappe.log_error(
            title=_("Tools List Error"),
            message=f"Error listing tools: {str(e)}"
        )
        raise


def _handle_tools_call(params: Dict[str, Any]) -> Dict[str, Any]:
    """Handle MCP tools/call request"""
    tool_name = params.get("name")
    arguments = params.get("arguments", {})
    
    if not tool_name:
        raise ValueError("Tool name is required")
    
    try:
        # Get tool registry
        registry = get_tool_registry()
        
        # Get tool instance
        tool = registry.get_tool(tool_name)
        if not tool:
            raise ValueError(f"Tool '{tool_name}' not found")
        
        # Execute tool
        result = tool.execute(arguments)
        
        # Convert result to MCP content format
        if isinstance(result, dict) and "success" in result:
            if result["success"]:
                # Success response
                content = []
                
                if "data" in result:
                    content.append({
                        "type": "text",
                        "text": json.dumps(result["data"], indent=2, default=str)
                    })
                elif "result" in result:
                    content.append({
                        "type": "text", 
                        "text": json.dumps(result["result"], indent=2, default=str)
                    })
                else:
                    # Extract meaningful content
                    filtered_result = {k: v for k, v in result.items() if k not in ["success"]}
                    content.append({
                        "type": "text",
                        "text": json.dumps(filtered_result, indent=2, default=str)
                    })
                
                return {"content": content}
            else:
                # Tool returned error
                raise ValueError(result.get("error", "Tool execution failed"))
        else:
            # Direct result
            content = [{
                "type": "text",
                "text": json.dumps(result, indent=2, default=str)
            }]
            return {"content": content}
            
    except Exception as e:
        frappe.log_error(
            title=_("Tool Execution Error"),
            message=f"Error executing tool '{tool_name}': {str(e)}"
        )
        raise


def _handle_ping(params: Dict[str, Any]) -> Dict[str, Any]:
    """Handle ping request for connection testing"""
    return {
        "status": "ok",
        "timestamp": frappe.utils.now(),
        "server": "frappe-assistant-core"
    }


def _create_success_response(request_id: Any, result: Dict[str, Any]) -> str:
    """Create JSON-RPC 2.0 success response"""
    response = {
        "jsonrpc": "2.0",
        "result": result,
        "id": request_id
    }
    return json.dumps(response)


def _create_error_response(request_id: Any, code: int, message: str, data: Any = None) -> str:
    """Create JSON-RPC 2.0 error response"""
    error = {
        "code": code,
        "message": message
    }
    
    if data is not None:
        error["data"] = data
    
    response = {
        "jsonrpc": "2.0",
        "error": error,
        "id": request_id
    }
    
    return json.dumps(response)


# Legacy compatibility - handle old endpoint names
@frappe.whitelist(allow_guest=False)
def handle_request(request_data: str) -> str:
    """Legacy compatibility wrapper"""
    return handle_mcp_request(request_data)


@frappe.whitelist(allow_guest=False)
def get_server_info() -> Dict[str, Any]:
    """Get server information for diagnostics"""
    try:
        registry = get_tool_registry()
        tools = registry.get_available_tools()
        
        return {
            "success": True,
            "server_info": {
                "name": "frappe-assistant-core",
                "version": get_app_version("frappe_assistant_core") or "1.0.0",
                "protocol_version": "2024-11-05",
                "total_tools": len(tools),
                "core_tools": len([t for t in tools if not hasattr(t, "plugin_name")]),
                "plugin_tools": len([t for t in tools if hasattr(t, "plugin_name")])
            }
        }
        
    except Exception as e:
        frappe.log_error(
            title=_("Server Info Error"),
            message=f"Error getting server info: {str(e)}"
        )
        
        return {
            "success": False,
            "error": str(e)
        }


@frappe.whitelist(allow_guest=False)
def validate_connection() -> Dict[str, Any]:
    """Validate MCP connection and permissions"""
    try:
        # Check basic permissions
        if not frappe.has_permission("System Manager") and not frappe.has_permission("Assistant Core Settings", "read"):
            frappe.throw(_("Insufficient permissions for MCP access"))
        
        # Test tool registry
        registry = get_tool_registry()
        tools = registry.get_available_tools()
        
        return {
            "success": True,
            "connection_valid": True,
            "user": frappe.session.user,
            "available_tools": len(tools),
            "message": "MCP connection validated successfully"
        }
        
    except Exception as e:
        return {
            "success": False,
            "connection_valid": False,
            "error": str(e)
        }