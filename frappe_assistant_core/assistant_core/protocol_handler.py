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

import json
import time
import frappe
from typing import Dict, Any, Optional
from frappe import _
from frappe.utils import now
from frappe_assistant_core.api.mcp import get_app_version

class assistantProtocolHandler:
    """Handles assistant JSON-RPC 2.0 protocol"""
    
    def __init__(self, client_id: str = None, user: str = None):
        self.client_id = client_id or frappe.generate_hash(length=8)
        self.user = user or frappe.session.user
        self.tools_registry = self._load_tools_registry()
        self.start_time = time.time()
    
    def process_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Process incoming assistant request"""
        start_time = time.time()
        
        # Validate JSON-RPC 2.0 format
        if not self._validate_jsonrpc_request(request):
            return self._error_response(-32600, "Invalid Request", request.get("id"))
        
        method = request.get("method")
        params = request.get("params", {})
        request_id = request.get("id")
        
        try:
            # Handle different assistant methods
            if method == "initialize":
                return self._handle_initialize(params, request_id)
            elif method == "tools/list":
                return self._handle_tools_list(request_id)
            elif method == "tools/call":
                return self._handle_tool_call(params, request_id, start_time)
            elif method == "resources/list":
                return self._handle_resources_list(request_id)
            elif method == "resources/read":
                return self._handle_resource_read(params, request_id)
            elif method == "notifications/initialized":
                return self._handle_initialized(request_id)
            else:
                return self._error_response(-32601, "Method not found", request_id)
                
        except Exception as e:
            frappe.log_error(f"assistant Protocol Error: {str(e)}", "assistant Protocol Handler")
            return self._error_response(-32603, "Internal error", request_id)
    
    def _handle_initialize(self, params: Dict[str, Any], request_id) -> Dict[str, Any]:
        """Handle assistant initialize request"""
        client_info = params.get("clientInfo", {})
        
        # Log initialization
        self._log_audit_entry(
            action="initialize",
            status="Success",
            input_data=json.dumps(params),
            output_data=json.dumps({"initialized": True})
        )
        
        return {
            "jsonrpc": "2.0",
            "result": {
                "protocolVersion": "2025-06-18",
                "capabilities": {
                    "tools": {
                        "listChanged": True
                    },
                    "resources": {
                        "subscribe": True,
                        "listChanged": True
                    },
                    "logging": {}
                },
                "serverInfo": {
                    "name": "Frappe Assistant Core",
                    "version": get_app_version("frappe_assistant_core") or "2.0.1"
                }
            },
            "id": request_id
        }
    
    def _handle_tools_list(self, request_id) -> Dict[str, Any]:
        """Handle tools/list request"""
        tools = []
        
        # Get available tools based on user permissions
        for tool_name, tool_config in self.tools_registry.items():
            if self._check_tool_access(tool_config):
                tools.append({
                    "name": tool_name,
                    "description": tool_config["description"], 
                    "inputSchema": tool_config["inputSchema"]
                })
        
        self._log_audit_entry(
            action="tools_list",
            status="Success",
            output_data=json.dumps({"tool_count": len(tools)})
        )
        
        return {
            "jsonrpc": "2.0",
            "result": {"tools": tools},
            "id": request_id
        }
    
    def _handle_tool_call(self, params: Dict[str, Any], request_id, start_time: float) -> Dict[str, Any]:
        """Handle tools/call request"""
        tool_name = params.get("name")
        arguments = params.get("arguments", {})
        
        if tool_name not in self.tools_registry:
            return self._error_response(-32602, f"Tool '{tool_name}' not found", request_id)
        
        tool_config = self.tools_registry[tool_name]
        
        # Check permissions
        if not self._check_tool_access(tool_config):
            # Map tool name to proper audit action
            action = self._get_audit_action(tool_name)
            self._log_audit_entry(
                action=action,
                tool_name=tool_name,
                status="Permission Denied",
                input_data=json.dumps(arguments),
                execution_time=time.time() - start_time
            )
            return self._error_response(-32603, "Permission denied", request_id)
        
        # Execute the tool
        try:
            result = self._execute_tool(tool_name, arguments)
            execution_time = time.time() - start_time
            
            # Log successful execution
            action = self._get_audit_action(tool_name)
            self._log_audit_entry(
                action=action,
                tool_name=tool_name,
                status="Success",
                input_data=json.dumps(arguments),
                output_data=json.dumps(result),
                execution_time=execution_time
            )
            
            # Update tool usage stats
            self._update_tool_stats(tool_name, success=True)
            
            return {
                "jsonrpc": "2.0",
                "result": result,
                "id": request_id
            }
            
        except Exception as e:
            execution_time = time.time() - start_time
            error_msg = str(e)
            
            # Log failed execution
            action = self._get_audit_action(tool_name)
            self._log_audit_entry(
                action=action,
                tool_name=tool_name,
                status="Error",
                input_data=json.dumps(arguments),
                error_message=error_msg,
                execution_time=execution_time
            )
            
            # Update tool usage stats
            self._update_tool_stats(tool_name, success=False)
            
            return self._error_response(-32603, f"Tool execution failed: {error_msg}", request_id)
    
    def _handle_resources_list(self, request_id) -> Dict[str, Any]:
        """Handle resources/list request"""
        resources = []
        
        # Add DocType resources
        doctypes = frappe.get_all("DocType", 
                                 filters={"custom": 0, "istable": 0}, 
                                 fields=["name", "description"])
        
        for dt in doctypes:
            if frappe.has_permission(dt.name, "read"):
                resources.append({
                    "uri": f"doctype://{dt.name}",
                    "name": dt.name,
                    "description": dt.description or f"DocType: {dt.name}",
                    "mimeType": "application/json"
                })
        
        return {
            "jsonrpc": "2.0",
            "result": {"resources": resources},
            "id": request_id
        }
    
    def _handle_resource_read(self, params: Dict[str, Any], request_id) -> Dict[str, Any]:
        """Handle resources/read request"""
        uri = params.get("uri")
        
        if not uri:
            return self._error_response(-32602, "URI is required", request_id)
        
        try:
            if uri.startswith("doctype://"):
                doctype_name = uri.replace("doctype://", "")
                doctype_info = frappe.get_meta(doctype_name)
                
                return {
                    "jsonrpc": "2.0",
                    "result": {
                        "contents": [{
                            "uri": uri,
                            "mimeType": "application/json",
                            "text": json.dumps({
                                "name": doctype_info.name,
                                "fields": [f.as_dict() for f in doctype_info.fields],
                                "permissions": doctype_info.permissions
                            }, indent=2)
                        }]
                    },
                    "id": request_id
                }
            else:
                return self._error_response(-32602, "Unsupported resource URI", request_id)
                
        except Exception as e:
            return self._error_response(-32603, f"Resource read failed: {str(e)}", request_id)
    
    def _handle_initialized(self, request_id) -> Dict[str, Any]:
        """Handle notifications/initialized"""
        return {
            "jsonrpc": "2.0",
            "result": {},
            "id": request_id
        }
    
    def _validate_jsonrpc_request(self, request: Dict[str, Any]) -> bool:
        """Validate JSON-RPC 2.0 request format"""
        if not isinstance(request, dict):
            return False
        
        if request.get("jsonrpc") != "2.0":
            return False
        
        if "method" not in request:
            return False
        
        return True
    
    def _load_tools_registry(self) -> Dict[str, Dict[str, Any]]:
        """Load tools from registry"""
        tools = {}
        
        registry_entries = frappe.get_all(
            "Assistant Tool Registry",
            filters={"enabled": 1},
            fields=["tool_name", "tool_description", "inputSchema", "required_permissions", "execution_timeout"]
        )
        
        for entry in registry_entries:
            try:
                inputSchema = json.loads(entry.inputSchema or "{}")
                required_permissions = json.loads(entry.required_permissions or "[]")
                
                tools[entry.tool_name] = {
                    "description": entry.tool_description,
                    "inputSchema": inputSchema,
                    "required_permissions": required_permissions,
                    "execution_timeout": entry.execution_timeout or 30
                }
            except json.JSONDecodeError:
                frappe.log_error(f"Invalid JSON in tool registry: {entry.tool_name}")
                continue
        
        return tools
    
    def _check_tool_access(self, tool_config: Dict[str, Any]) -> bool:
        """Check if current user can access the tool"""
        required_permissions = tool_config.get("required_permissions", [])
        
        if not required_permissions:
            return True
        
        user_roles = frappe.get_roles(self.user)
        
        for perm in required_permissions:
            if isinstance(perm, dict):
                # DocType permission check
                doctype = perm.get("doctype")
                ptype = perm.get("permission", "read")
                if not frappe.has_permission(doctype, ptype, user=self.user):
                    return False
            elif isinstance(perm, str):
                # Role-based permission check
                if perm not in user_roles:
                    return False
        
        return True
    
    def _execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool with given arguments"""
        # Import and execute the appropriate tool
        if tool_name.startswith("document_"):
            from frappe_assistant_core.tools.document_tools import DocumentTools
            return DocumentTools.execute_tool(tool_name, arguments)
        elif tool_name.startswith("report_"):
            from frappe_assistant_core.tools.report_tools import ReportTools
            return ReportTools.execute_tool(tool_name, arguments)
        elif tool_name.startswith("search_"):
            from frappe_assistant_core.tools.search_tools import SearchTools
            return SearchTools.execute_tool(tool_name, arguments)
        elif tool_name.startswith("metadata_"):
            from frappe_assistant_core.tools.metadata_tools import MetadataTools
            return MetadataTools.execute_tool(tool_name, arguments)
        elif tool_name.startswith("execute_") or tool_name.startswith("analyze_") or tool_name.startswith("query_") or tool_name.startswith("create_visualization"):
            from frappe_assistant_core.tools.analysis_tools import AnalysisTools
            return AnalysisTools.execute_tool(tool_name, arguments)
        else:
            raise Exception(f"Unknown tool category for: {tool_name}")
    
    def _update_tool_stats(self, tool_name: str, success: bool):
        """Update tool usage statistics"""
        try:
            tool_doc = frappe.get_doc("Assistant Tool Registry", tool_name)
            tool_doc.update_usage_stats(success=success)
        except Exception:
            pass  # Ignore stats update errors
    
    def _get_audit_action(self, tool_name: str) -> str:
        """Map tool name to valid audit log action"""
        tool_action_mapping = {
            "document_get": "get_document",
            "document_list": "search_documents", 
            "document_create": "create_document",
            "document_update": "update_document",
            "document_delete": "delete_document",
            "document_submit": "update_document",
            "report_execute": "run_report",
            "metadata_doctype": "get_metadata",
            "metadata_get": "get_metadata"
        }
        
        # Get the appropriate action, default to custom_tool
        return tool_action_mapping.get(tool_name, "custom_tool")
    
    def _log_audit_entry(self, action: str, status: str, tool_name: str = None, 
                        input_data: str = None, output_data: str = None, 
                        error_message: str = None, execution_time: float = None):
        """Log audit entry"""
        try:
            frappe.get_doc({
                "doctype": "Assistant Audit Log",
                "action": action,
                "tool_name": tool_name,
                "user": self.user,
                "status": status,
                "execution_time": execution_time,
                "timestamp": now(),
                "client_id": self.client_id,
                "ip_address": frappe.local.request_ip if hasattr(frappe.local, 'request_ip') else None,
                "input_data": input_data,
                "output_data": output_data,
                "error_message": error_message
            }).insert(ignore_permissions=True)
        except Exception:
            pass  # Ignore audit logging errors
    
    def _error_response(self, code: int, message: str, request_id: Any) -> Dict[str, Any]:
        """Create JSON-RPC error response"""
        return {
            "jsonrpc": "2.0",
            "error": {
                "code": code,
                "message": message
            },
            "id": request_id
        }