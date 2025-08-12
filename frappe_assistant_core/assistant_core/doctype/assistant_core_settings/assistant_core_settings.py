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

import frappe
from frappe.model.document import Document
from frappe import _
from frappe_assistant_core.assistant_core.server import assistantServer

class AssistantCoreSettings(Document):
    """assistant Server Settings DocType controller"""
    
    def validate(self):
        """Validate settings before saving"""
        # Currently no validation needed as removed unused fields
        # Plugin validation is handled by plugin manager
        # Streaming settings have reasonable defaults
        pass
    
    
    def restart_assistant_core(self):
        """Restart the assistant MCP API with new settings"""
        try:
            # Disable existing API
            self.disable_assistant_api()
            
            # Enable API with new settings
            self.enable_assistant_api()
            
            frappe.msgprint("assistant MCP API restarted successfully")
            
        except Exception as e:
            frappe.log_error(f"Failed to restart assistant MCP API: {str(e)}")
            frappe.throw(f"Failed to restart assistant MCP API: {str(e)}")
    
    def enable_assistant_api(self):
        """Enable the assistant MCP API"""
        try:
            server = assistantServer()
            server.enable()
            
            # Log the API enable (skip if DocType doesn't exist)
            try:
                if frappe.db.table_exists("tabAssistant Connection Log"):
                    frappe.get_doc({
                        "doctype": "Assistant Connection Log",
                        "action": "api_enabled",
                        "user": frappe.session.user,
                        "details": "assistant MCP API enabled"
                    }).insert(ignore_permissions=True)
            except:
                pass  # Don't fail API enable if logging fails
            
        except Exception as e:
            frappe.log_error(f"Failed to enable assistant MCP API: {str(e)}")
            raise
    
    def disable_assistant_api(self):
        """Disable the assistant MCP API"""
        try:
            server = assistantServer()
            server.disable()
            
            # Log the API disable (skip if DocType doesn't exist)
            try:
                if frappe.db.table_exists("tabAssistant Connection Log"):
                    frappe.get_doc({
                        "doctype": "Assistant Connection Log",
                        "action": "api_disabled",
                        "user": frappe.session.user,
                        "details": "assistant MCP API disabled"
                    }).insert(ignore_permissions=True)
            except:
                pass  # Don't fail API disable if logging fails
            
        except Exception as e:
            frappe.log_error(f"Failed to disable assistant MCP API: {str(e)}")
            raise
    
    # Legacy function names for backward compatibility
    def start_assistant_core(self):
        """Legacy: Enable the assistant MCP API"""
        return self.enable_assistant_api()
    
    def stop_assistant_core(self):
        """Legacy: Disable the assistant MCP API"""
        return self.disable_assistant_api()
    
    def get_streaming_protocol(self):
        """Get current streaming protocol configuration"""
        # Check if streaming-related fields exist in the DocType
        streaming_config = {
            "artifact_streaming_enforced": True,  # Default to enforced
            "protocol_status": "active",
            "limit_prevention_active": True,
            "streaming_behavior_instructions": """
Always create analysis workspace artifacts before performing data analysis.
Stream all detailed work to artifacts to prevent response limits.
Keep responses minimal with artifact references.
Build unlimited analysis depth via progressive artifact updates.
            """
        }
        
        # If fields exist in DocType, use their values
        if hasattr(self, "enforce_artifact_streaming"):
            streaming_config["artifact_streaming_enforced"] = self.enforce_artifact_streaming
            streaming_config["protocol_status"] = "active" if self.enforce_artifact_streaming else "optional"
        
        if hasattr(self, "response_limit_prevention"):
            streaming_config["limit_prevention_active"] = self.response_limit_prevention
            
        if hasattr(self, "streaming_behavior_instructions"):
            streaming_config["custom_instructions"] = self.streaming_behavior_instructions
        
        return streaming_config
    
    def get_enhanced_settings(self):
        """Get all settings including streaming protocol"""
        settings = self.as_dict()
        settings["streaming_protocol"] = self.get_streaming_protocol()
        return settings
    
    @frappe.whitelist()
    def refresh_plugins(self):
        """Refresh the entire plugin system - discovery and tools"""
        try:
            from frappe_assistant_core.utils.plugin_manager import get_plugin_manager
            
            # Refresh plugin manager discovery
            plugin_manager = get_plugin_manager()
            plugin_manager.refresh_plugins()
            
            # Get statistics
            discovered_plugins = plugin_manager.get_discovered_plugins()
            enabled_plugins = plugin_manager.get_enabled_plugins()
            available_tools = plugin_manager.get_all_tools()
            
            frappe.msgprint(
                frappe._("Plugin system refreshed successfully.<br>Found {0} tools from {1} plugins.<br>Plugins: {2} enabled out of {3} discovered.").format(
                    len(available_tools),
                    len(enabled_plugins),
                    len(enabled_plugins),
                    len(discovered_plugins)
                )
            )
            
            return {
                "success": True,
                "stats": {
                    "total_tools": len(available_tools),
                    "discovered_plugins": len(discovered_plugins),
                    "enabled_plugins": len(enabled_plugins)
                }
            }
            
        except Exception as e:
            frappe.log_error(
                title=frappe._("Plugin Refresh Error"),
                message=str(e)
            )
            frappe.throw(
                frappe._("Failed to refresh plugin system: {0}").format(str(e))
            )
    
    
    def on_update(self):
        """Handle settings update"""
        from frappe_assistant_core.assistant_core.server import get_server_instance
        
        server = get_server_instance()
        server_was_enabled = self.has_value_changed('server_enabled')
        
        # Handle MCP API enable/disable
        if self.server_enabled:
            if server_was_enabled or not server.running:
                # Enable API if it was just enabled or not running
                frappe.enqueue('frappe_assistant_core.assistant_core.server.enable_background_api', queue='short')
        else:
            if server_was_enabled and server.running:
                # Disable API if it was just disabled
                self.disable_assistant_api()
        
        # Refresh tool registry if settings changed
        try:
            from frappe_assistant_core.utils.tool_cache import refresh_tool_cache
            refresh_tool_cache()
        except Exception as e:
            frappe.log_error(
                title=frappe._("Tool Cache Refresh Error"),
                message=str(e)
            )
    
    @frappe.whitelist()
    def get_plugin_status(self):
        """Get plugin status with enhanced tool details and controls"""
        try:
            from frappe_assistant_core.utils.plugin_manager import get_plugin_manager
            
            # Get plugin manager for plugin info
            plugin_manager = get_plugin_manager()
            discovered_plugins = plugin_manager.get_discovered_plugins()
            enabled_plugins = plugin_manager.get_enabled_plugins()
            available_tools = plugin_manager.get_all_tools()
            
            # Get external tools from hooks
            external_tools = {}
            try:
                assistant_tools_hooks = frappe.get_hooks("assistant_tools") or []
                for tool_path in assistant_tools_hooks:
                    try:
                        parts = tool_path.rsplit('.', 1)
                        if len(parts) == 2:
                            module_path, class_name = parts
                            module = __import__(module_path, fromlist=[class_name])
                            tool_class = getattr(module, class_name)
                            tool_instance = tool_class()
                            tool_name = getattr(tool_instance, "name", parts[0].split('.')[-1])
                            source_app = getattr(tool_instance, "source_app", parts[0].split('.')[0])
                            
                            external_tools[tool_name] = {
                                'name': tool_name,
                                'description': getattr(tool_instance, "description", "External tool"),
                                'source_app': source_app,
                                'plugin_name': 'custom_tools'  # Associate with custom_tools plugin
                            }
                    except Exception as e:
                        frappe.log_error(
                            title=frappe._("Failed to load external tool"),
                            message=f"Tool: {tool_path}\nError: {str(e)}"
                        )
            except Exception as e:
                frappe.log_error(
                    title=frappe._("Failed to get external tools"),
                    message=str(e)
                )
            
            # Build HTML with enhanced plugin controls
            html_parts = []
            
            # Overall statistics header with enhanced info
            # Count plugin tools that are in enabled plugins
            active_plugin_tools = len([tool_name for tool_name, tool_info in available_tools.items() 
                                      if tool_info.plugin_name in enabled_plugins])
            
            # Add external tools count if custom_tools plugin is enabled
            active_external_tools = len(external_tools) if "custom_tools" in enabled_plugins else 0
            
            # Total active tools - external tools are shown as part of custom_tools plugin
            active_tools = active_plugin_tools + active_external_tools
            total_tools = len(available_tools) + len(external_tools)
            
            html_parts.append(f"""
            <div class="alert alert-info mb-3">
                <div class="row align-items-center">
                    <div class="col-md-8">
                        <h5><i class="fa fa-cogs text-primary"></i> Plugin System Status</h5>
                        <div class="row mt-2">
                            <div class="col-md-4"><strong>Active Tools:</strong> <span class="badge badge-success">{active_tools}</span> / {total_tools}</div>
                            <div class="col-md-4"><strong>Plugins:</strong> <span class="badge badge-primary">{len(enabled_plugins)}</span> / {len(discovered_plugins)}</div>
                            <div class="col-md-4"><strong>Status:</strong> <span class="text-success"><i class="fa fa-check-circle"></i> Operational</span></div>
                        </div>
                    </div>
                    <div class="col-md-4 text-right">
                        <button type="button" class="btn btn-sm btn-outline-primary" onclick="window.toggleToolDetails()" id="toggle-details-btn">
                            <i class="fa fa-eye"></i> Show Tool Details
                        </button>
                    </div>
                </div>
            </div>
            """)
            
            # Plugin management section
            html_parts.append("""
            <div class="card">
                <div class="card-header">
                    <h6><i class="fa fa-puzzle-piece"></i> Plugin Management</h6>
                    <small class="text-muted">Enable or disable plugins to control available tools</small>
                </div>
                <div class="card-body">
            """)
            
            # Individual plugin cards with enhanced tool details
            for plugin in discovered_plugins:
                plugin_name = plugin.get('name', 'Unknown')
                is_enabled = plugin_name in enabled_plugins
                plugin_tools = plugin.get('tools', [])
                
                # For custom_tools plugin, use external tools count
                if plugin_name == 'custom_tools':
                    tools_count = len(external_tools)
                    active_tool_count = len(external_tools) if is_enabled else 0
                else:
                    tools_count = len(plugin_tools)
                    active_tool_count = len(plugin_tools) if plugin_name in enabled_plugins else 0
                
                status_badge = "badge-success" if is_enabled else "badge-secondary"
                status_text = "Active" if is_enabled else "Inactive"
                toggle_action = "disable" if is_enabled else "enable"
                toggle_class = "btn-outline-warning" if is_enabled else "btn-outline-success"
                toggle_icon = "fa-pause" if is_enabled else "fa-play"
                
                # Plugin category icon
                category_icons = {
                    'core': 'fa-database',
                    'data_science': 'fa-chart-bar', 
                    'visualization': 'fa-chart-pie',
                    'workflow': 'fa-sitemap',
                    'integration': 'fa-plug'
                }
                plugin_icon = category_icons.get(plugin_name, 'fa-puzzle-piece')
                
                html_parts.append(f"""
                <div class="plugin-card border rounded p-3 mb-3" style="background: {'#f8f9fa' if is_enabled else '#ffffff'}; border-left: 4px solid {'#28a745' if is_enabled else '#6c757d'};">
                    <div class="row align-items-center">
                        <div class="col-md-9">
                            <div class="d-flex align-items-center mb-2">
                                <i class="fa {plugin_icon} text-primary mr-2" style="font-size: 1.2em;"></i>
                                <h6 class="mb-0">
                                    {plugin.get('display_name', plugin_name.replace('_', ' ').title())}
                                    <span class="badge {status_badge} ml-2">{status_text}</span>
                                </h6>
                            </div>
                            <p class="text-muted mb-2 small">{plugin.get('description', 'Advanced tools and functionality for Frappe Assistant')}</p>
                            <div class="d-flex align-items-center">
                                <small class="text-info mr-3">
                                    <i class="fa fa-tools"></i> {active_tool_count}/{tools_count} tools active
                                </small>
                                <small class="text-muted mr-3">
                                    <i class="fa fa-tag"></i> v{plugin.get('version', '1.0.0')}
                                </small>
                                <small class="text-success">
                                    <i class="fa fa-shield-alt"></i> Verified
                                </small>
                            </div>
                        </div>
                        <div class="col-md-3 text-right">
                            <div class="btn-group-vertical" style="width: 100%;">
                                <button type="button" 
                                        class="btn {toggle_class} btn-sm mb-1" 
                                        onclick="window.togglePlugin('{plugin_name}', '{toggle_action}')"
                                        style="font-size: 0.8em;">
                                    <i class="fa {toggle_icon}"></i> {toggle_action.title()}
                                </button>
                                <button type="button" 
                                        class="btn btn-outline-info btn-sm tool-details-btn" 
                                        onclick="window.togglePluginTools('{plugin_name}')"
                                        style="font-size: 0.75em;">
                                    <i class="fa fa-list"></i> Tools ({tools_count})
                                </button>
                            </div>
                        </div>
                    </div>
                    
                    <!-- Tool Details Panel (Initially Hidden) -->
                    <div class="plugin-tools-panel mt-3" id="tools-{plugin_name}" style="display: none;">
                        <hr class="mt-2 mb-3">
                        <h6 class="mb-2"><i class="fa fa-tools text-muted"></i> Available Tools</h6>
                        <div class="row">
                """)
                
                # Add individual tool cards within plugin
                # For custom_tools plugin, show external tools
                if plugin_name == 'custom_tools':
                    external_tool_names = list(external_tools.keys())
                    if external_tool_names:
                        for tool_name in external_tool_names[:6]:  # Show max 6 tools initially
                            tool_status = "success" if is_enabled else "secondary"
                            tool_icon = "fa-check-circle" if is_enabled else "fa-circle"
                            
                            html_parts.append(f"""
                                <div class="col-md-6 mb-2">
                                    <div class="small p-2 border rounded" style="background: #f8f9fa;">
                                        <div class="d-flex justify-content-between align-items-center">
                                            <span>
                                                <i class="fa {tool_icon} text-{tool_status}"></i>
                                                <strong>{tool_name.replace('_', ' ').title()}</strong>
                                            </span>
                                            <span class="badge badge-{tool_status} badge-sm">
                                                {'Active' if is_enabled else 'Inactive'}
                                            </span>
                                        </div>
                                    </div>
                                </div>
                            """)
                        
                        if len(external_tool_names) > 6:
                            html_parts.append(f"""
                                <div class="col-12">
                                    <small class="text-muted">
                                        <i class="fa fa-plus"></i> And {len(external_tool_names) - 6} more tools...
                                    </small>
                                </div>
                            """)
                    else:
                        html_parts.append("""
                            <div class="col-12">
                                <small class="text-muted">No external tools available</small>
                            </div>
                        """)
                elif plugin_tools:
                    for plugin_tool in plugin_tools[:6]:  # Show max 6 tools initially
                        tool_status = "success" if is_enabled else "secondary"
                        tool_icon = "fa-check-circle" if is_enabled else "fa-circle"
                        
                        html_parts.append(f"""
                            <div class="col-md-6 mb-2">
                                <div class="small p-2 border rounded" style="background: #f8f9fa;">
                                    <div class="d-flex justify-content-between align-items-center">
                                        <span>
                                            <i class="fa {tool_icon} text-{tool_status}"></i>
                                            <strong>{plugin_tool.replace('_', ' ').title()}</strong>
                                        </span>
                                        <span class="badge badge-{tool_status} badge-sm">
                                            {'Active' if is_enabled else 'Inactive'}
                                        </span>
                                    </div>
                                </div>
                            </div>
                        """)
                    
                    if len(plugin_tools) > 6:
                        html_parts.append(f"""
                            <div class="col-12">
                                <small class="text-muted">
                                    <i class="fa fa-plus"></i> And {len(plugin_tools) - 6} more tools...
                                </small>
                            </div>
                        """)
                else:
                    html_parts.append("""
                        <div class="col-12">
                            <small class="text-muted">No tools available in this plugin</small>
                        </div>
                    """)
                
                html_parts.append("""
                        </div>
                    </div>
                </div>
                """)
            
            html_parts.append("""
                </div>
            </div>
            """)
            
            # Tools breakdown by plugin with search and filter
            if available_tools or external_tools:
                # Only count external tools for Tool Explorer if not already in available_tools
                explorer_tool_count = len(available_tools) + len(external_tools)
                html_parts.append(f"""
                <div class="card mt-3">
                    <div class="card-header">
                        <div class="row align-items-center">
                            <div class="col-md-6">
                                <h6 class="mb-0"><i class="fa fa-search"></i> Tool Explorer ({explorer_tool_count} tools)</h6>
                            </div>
                            <div class="col-md-6">
                                <div class="input-group input-group-sm">
                                    <input type="text" class="form-control" id="tool-search" 
                                           placeholder="Search tools..." onkeyup="window.filterTools()">
                                    <div class="input-group-append">
                                        <select class="form-control" id="plugin-filter" onchange="window.filterTools()">
                                            <option value="">All Plugins</option>
                                            <option value="active">Active Only</option>
                                            <option value="inactive">Inactive Only</option>
                                        </select>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                    <div class="card-body" style="max-height: 400px; overflow-y: auto;">
                        <div class="row" id="tools-container">
                """)
                
                # Display individual tools with detailed information
                for tool_name, tool_info in available_tools.items():
                    plugin_name = tool_info.plugin_name
                    is_plugin_enabled = plugin_name in enabled_plugins
                    tool_status = "success" if is_plugin_enabled else "secondary"
                    tool_status_text = "Active" if is_plugin_enabled else "Inactive"
                    
                    # Get tool description if available
                    tool_desc = "Advanced tool functionality"  # Default description
                    try:
                        if hasattr(tool_info, 'description'):
                            tool_desc = tool_info.description[:100] + "..." if len(tool_info.description) > 100 else tool_info.description
                    except:
                        pass
                    
                    html_parts.append(f"""
                    <div class="col-md-6 mb-3 tool-item" 
                         data-tool-name="{tool_name.lower()}" 
                         data-plugin="{plugin_name.lower()}" 
                         data-status="{'active' if is_plugin_enabled else 'inactive'}">
                        <div class="border rounded p-3 h-100" style="background: {'#f8f9fa' if is_plugin_enabled else '#ffffff'};">
                            <div class="d-flex justify-content-between align-items-start mb-2">
                                <h6 class="mb-1">
                                    <i class="fa fa-tool text-primary"></i>
                                    {tool_name.replace('_', ' ').title()}
                                </h6>
                                <span class="badge badge-{tool_status}">{tool_status_text}</span>
                            </div>
                            <p class="text-muted small mb-2">{tool_desc}</p>
                            <div class="d-flex justify-content-between align-items-center">
                                <small class="text-info">
                                    <i class="fa fa-puzzle-piece"></i> {plugin_name.replace('_', ' ').title()}
                                </small>
                                <small class="text-muted">
                                    <i class="fa fa-{'check-circle' if is_plugin_enabled else 'times-circle'}"></i>
                                    {'Ready' if is_plugin_enabled else 'Disabled'}
                                </small>
                            </div>
                        </div>
                    </div>
                    """)
                
                # Add external tools to the Tool Explorer
                for tool_name, tool_data in external_tools.items():
                    is_plugin_enabled = "custom_tools" in enabled_plugins
                    tool_status = "success" if is_plugin_enabled else "secondary"
                    tool_status_text = "Active" if is_plugin_enabled else "Inactive"
                    
                    # Get tool description
                    tool_desc = tool_data.get('description', 'External tool')
                    if len(tool_desc) > 100:
                        tool_desc = tool_desc[:100] + "..."
                    
                    html_parts.append(f"""
                    <div class="col-md-6 mb-3 tool-item" 
                         data-tool-name="{tool_name.lower()}" 
                         data-plugin="{tool_data.get('source_app', 'custom_tools').lower()}" 
                         data-status="{'active' if is_plugin_enabled else 'inactive'}">
                        <div class="border rounded p-3 h-100" style="background: {'#f8f9fa' if is_plugin_enabled else '#ffffff'};">
                            <div class="d-flex justify-content-between align-items-start mb-2">
                                <h6 class="mb-1">
                                    <i class="fa fa-tool text-primary"></i>
                                    {tool_name.replace('_', ' ').title()}
                                </h6>
                                <span class="badge badge-{tool_status}">{tool_status_text}</span>
                            </div>
                            <p class="text-muted small mb-2">{tool_desc}</p>
                            <div class="d-flex justify-content-between align-items-center">
                                <small class="text-info">
                                    <i class="fa fa-puzzle-piece"></i> {tool_data.get('source_app', 'External').replace('_', ' ').title()}
                                </small>
                                <small class="text-muted">
                                    <i class="fa fa-{'check-circle' if is_plugin_enabled else 'times-circle'}"></i>
                                    {'Ready' if is_plugin_enabled else 'Disabled'}
                                </small>
                            </div>
                        </div>
                    </div>
                    """)
                
                html_parts.append("""
                        </div>
                    </div>
                </div>
                """)
            
            # Show error plugins (if any)
            error_plugins = [p for p in discovered_plugins if not p.get('can_enable', True)]
            if error_plugins:
                html_parts.append("""
                <div class="alert alert-warning mt-3">
                    <h6><i class="fa fa-exclamation-triangle"></i> Plugin Issues</h6>
                    <ul class="mb-0">
                """)
                for plugin in error_plugins[:3]:
                    error_msg = plugin.get('validation_error', 'Unknown error')
                    html_parts.append(f"<li><strong>{plugin.get('name', 'Unknown')}:</strong> {error_msg}</li>")
                if len(error_plugins) > 3:
                    html_parts.append(f"<li><em>... and {len(error_plugins) - 3} more plugin errors</em></li>")
                html_parts.append("</ul></div>")
            
            # Add enhanced JavaScript for plugin and tool management
            html_parts.append("""
            <style>
            .plugin-card {
                transition: all 0.3s ease;
                position: relative;
            }
            .plugin-card:hover {
                transform: translateY(-2px);
                box-shadow: 0 4px 12px rgba(0,0,0,0.1);
            }
            .tool-details-btn:hover {
                transform: scale(1.05);
            }
            .plugin-tools-panel {
                animation: fadeIn 0.3s ease;
            }
            @keyframes fadeIn {
                from { opacity: 0; height: 0; }
                to { opacity: 1; height: auto; }
            }
            .badge-sm {
                font-size: 0.7em;
                padding: 0.2em 0.4em;
            }
            </style>
            
            <script>
            // Avoid redeclaration by checking existence
            if (typeof window.toolDetailsVisible === 'undefined') {
                window.toolDetailsVisible = false;
            }
            
            // Only define functions if they don't exist
            if (typeof window.togglePlugin === 'undefined') {
                window.togglePlugin = function(pluginName, action) {
                frappe.call({
                    method: 'toggle_plugin',
                    doc: cur_frm.doc,
                    args: {
                        plugin_name: pluginName,
                        action: action
                    },
                    freeze: true,
                    freeze_message: __('Updating plugin...'),
                    callback: function(response) {
                        if (!response.exc) {
                            cur_frm.reload_doc();
                            frappe.show_alert({
                                message: __('Plugin {0} {1}d successfully', [pluginName, action]),
                                indicator: 'green'
                            });
                        } else {
                            frappe.show_alert({
                                message: __('Failed to {0} plugin {1}', [action, pluginName]),
                                indicator: 'red'
                            });
                        }
                    }
                });
            };
            }
            
            if (typeof window.togglePluginTools === 'undefined') {
                window.togglePluginTools = function(pluginName) {
                const panel = document.getElementById('tools-' + pluginName);
                const btn = event.target.closest('button');
                
                if (panel.style.display === 'none') {
                    panel.style.display = 'block';
                    btn.innerHTML = '<i class="fa fa-list"></i> Hide Tools';
                    btn.classList.remove('btn-outline-info');
                    btn.classList.add('btn-info');
                } else {
                    panel.style.display = 'none';
                    btn.innerHTML = '<i class="fa fa-list"></i> Tools (' + panel.querySelectorAll('.col-md-6').length + ')';
                    btn.classList.remove('btn-info');
                    btn.classList.add('btn-outline-info');
                }
            };
            }
            
            if (typeof window.toggleToolDetails === 'undefined') {
                window.toggleToolDetails = function() {
                window.toolDetailsVisible = !window.toolDetailsVisible;
                const btn = document.getElementById('toggle-details-btn');
                const panels = document.querySelectorAll('.plugin-tools-panel');
                
                if (window.toolDetailsVisible) {
                    panels.forEach(panel => panel.style.display = 'block');
                    btn.innerHTML = '<i class="fa fa-eye-slash"></i> Hide Tool Details';
                    btn.classList.remove('btn-outline-primary');
                    btn.classList.add('btn-primary');
                } else {
                    panels.forEach(panel => panel.style.display = 'none');
                    btn.innerHTML = '<i class="fa fa-eye"></i> Show Tool Details';
                    btn.classList.remove('btn-primary');
                    btn.classList.add('btn-outline-primary');
                    
                    // Reset individual tool buttons
                    document.querySelectorAll('.tool-details-btn').forEach(toolBtn => {
                        toolBtn.innerHTML = toolBtn.innerHTML.replace('Hide Tools', 'Tools');
                        toolBtn.classList.remove('btn-info');
                        toolBtn.classList.add('btn-outline-info');
                    });
                }
            };
            }
            
            // Tool filtering and search functionality
            if (typeof window.filterTools === 'undefined') {
                window.filterTools = function() {
                const searchTerm = document.getElementById('tool-search').value.toLowerCase();
                const pluginFilter = document.getElementById('plugin-filter').value;
                const toolItems = document.querySelectorAll('.tool-item');
                let visibleCount = 0;
                
                toolItems.forEach(item => {
                    const toolName = item.getAttribute('data-tool-name');
                    const pluginName = item.getAttribute('data-plugin');
                    const status = item.getAttribute('data-status');
                    
                    let showItem = true;
                    
                    // Apply search filter
                    if (searchTerm && !toolName.includes(searchTerm) && !pluginName.includes(searchTerm)) {
                        showItem = false;
                    }
                    
                    // Apply plugin status filter
                    if (pluginFilter) {
                        if (pluginFilter === 'active' && status !== 'active') showItem = false;
                        if (pluginFilter === 'inactive' && status !== 'inactive') showItem = false;
                    }
                    
                    item.style.display = showItem ? 'block' : 'none';
                    if (showItem) visibleCount++;
                });
                
                // Update the count in header
                const header = document.querySelector('#tools-container').closest('.card').querySelector('h6');
                if (header) {
                    const totalTools = toolItems.length;
                    header.innerHTML = `<i class="fa fa-search"></i> Tool Explorer (${visibleCount}/${totalTools} tools)`;
                }
            };
            }
            
            // Auto-refresh disabled to prevent UI state loss
            // Note: Plugin status updates when form is manually refreshed
            // This prevents expanded sections from auto-collapsing
            </script>
            """)
            
            return {"success": True, "html": "".join(html_parts)}
            
        except Exception as e:
            return {
                "success": False, 
                "html": f"<div class='alert alert-danger'>Error loading plugin status: {str(e)}</div>"
            }
    
    @frappe.whitelist()
    def toggle_plugin(self, plugin_name, action):
        """Enable or disable a plugin"""
        try:
            from frappe_assistant_core.utils.plugin_manager import get_plugin_manager, PluginError
            
            plugin_manager = get_plugin_manager()
            
            if action == "enable":
                result = plugin_manager.enable_plugin(plugin_name)
                message = f"Plugin '{plugin_name}' enabled successfully"
            elif action == "disable":
                result = plugin_manager.disable_plugin(plugin_name)
                message = f"Plugin '{plugin_name}' disabled successfully"
            else:
                frappe.throw(f"Invalid action: {action}")
            
            if result:
                frappe.msgprint(frappe._(message))
                return {"success": True, "message": message}
            else:
                error_msg = f"Failed to {action} plugin '{plugin_name}'"
                frappe.throw(error_msg)
                
        except PluginError as e:
            frappe.log_error(
                title=frappe._("Plugin Toggle Error"),
                message=str(e)
            )
            frappe.throw(frappe._(str(e)))
        except Exception as e:
            frappe.log_error(
                title=frappe._("Plugin Toggle Error"),
                message=str(e)
            )
            frappe.throw(
                frappe._("Failed to {0} plugin '{1}': {2}").format(action, plugin_name, str(e))
            )



def get_context(context):
    context.title = _("assistant Server Settings")
    context.docs = _("Manage the settings for the assistant Server.")
    context.settings = frappe.get_doc("Assistant Core Settings")