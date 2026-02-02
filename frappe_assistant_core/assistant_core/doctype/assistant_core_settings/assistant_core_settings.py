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
from frappe import _
from frappe.model.document import Document

from frappe_assistant_core.assistant_core.server import assistantServer


class AssistantCoreSettings(Document):
    """assistant Server Settings DocType controller"""

    def onload(self):
        """Populate computed fields when document is loaded (including first time after install)"""
        self._populate_endpoint_urls()

    def before_save(self):
        """Populate computed fields before saving"""
        self._populate_endpoint_urls()

    def _populate_endpoint_urls(self):
        """Helper to populate endpoint URLs based on current site"""
        frappe_url = frappe.utils.get_url()
        self.mcp_endpoint_url = f"{frappe_url}/api/method/frappe_assistant_core.api.fac_endpoint.handle_mcp"
        self.oauth_discovery_url = f"{frappe_url}/.well-known/openid-configuration"

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
            frappe.throw(_("Failed to restart assistant MCP API: {0}").format(str(e)))

    def enable_assistant_api(self):
        """Enable the assistant MCP API"""
        try:
            server = assistantServer()
            server.enable()

        except Exception as e:
            frappe.log_error(f"Failed to enable assistant MCP API: {str(e)}")
            raise

    def disable_assistant_api(self):
        """Disable the assistant MCP API"""
        try:
            server = assistantServer()
            server.disable()

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

    @frappe.whitelist()
    def get_mcp_server_info(self):
        """Get MCP server information (for backward compatibility with MCP Inspector)"""
        from frappe_assistant_core import hooks

        frappe_url = frappe.utils.get_url()
        return {
            "mcp_endpoint": f"{frappe_url}/api/method/frappe_assistant_core.api.fac_endpoint.handle_mcp",
            "mcp_transport": "StreamableHTTP",
            "mcp_protocol_version": "2025-03-26",
            "server_enabled": self.server_enabled,
            "server_info": {
                "name": hooks.app_name,
                "version": hooks.app_version,
                "description": hooks.app_description,
                "title": hooks.app_title,
                "publisher": hooks.app_publisher,
            },
        }

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
            """,
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

    # SSE Bridge methods removed - SSE transport is deprecated
    # Use StreamableHTTP (OAuth-based) transport instead

    @frappe.whitelist()
    def refresh_plugins(self):
        """Refresh the entire plugin system - discovery and tools"""
        try:
            from frappe_assistant_core.core.tool_registry import get_tool_registry
            from frappe_assistant_core.utils.plugin_manager import get_plugin_manager

            # Refresh plugin manager discovery
            plugin_manager = get_plugin_manager()
            plugin_manager.refresh_plugins()

            # Get statistics
            discovered_plugins = plugin_manager.get_discovered_plugins()
            enabled_plugins = plugin_manager.get_enabled_plugins()
            available_tools = plugin_manager.get_all_tools()

            # Include external tools from hooks
            tool_registry = get_tool_registry()
            external_tools = tool_registry._get_external_tools()
            available_tools.update(external_tools)

            frappe.msgprint(
                frappe._(
                    "Plugin system refreshed successfully.<br>Found {0} tools from {1} plugins.<br>Plugins: {2} enabled out of {3} discovered."
                ).format(
                    len(available_tools), len(enabled_plugins), len(enabled_plugins), len(discovered_plugins)
                )
            )

            return {
                "success": True,
                "stats": {
                    "total_tools": len(available_tools),
                    "discovered_plugins": len(discovered_plugins),
                    "enabled_plugins": len(enabled_plugins),
                },
            }

        except Exception as e:
            frappe.log_error(title=frappe._("Plugin Refresh Error"), message=str(e))
            frappe.throw(frappe._("Failed to refresh plugin system: {0}").format(str(e)))

    def on_update(self):
        """Handle settings update"""
        from frappe_assistant_core.assistant_core.server import get_server_instance

        server = get_server_instance()
        server_was_enabled = self.has_value_changed("server_enabled")

        # Handle MCP API enable/disable
        if self.server_enabled:
            if server_was_enabled or not server.running:
                # Enable API if it was just enabled or not running
                frappe.enqueue(
                    "frappe_assistant_core.assistant_core.server.enable_background_api", queue="short"
                )
        else:
            if server_was_enabled and server.running:
                # Disable API if it was just disabled
                self.disable_assistant_api()

        # Refresh tool registry if settings changed
        try:
            from frappe_assistant_core.utils.tool_cache import refresh_tool_cache

            refresh_tool_cache()
        except Exception as e:
            frappe.log_error(title=frappe._("Tool Cache Refresh Error"), message=str(e))

    @frappe.whitelist()
    def get_plugin_status(self):
        """Get plugin status with a simplified view that links to FAC Admin for full control"""
        try:
            from frappe_assistant_core.core.tool_registry import get_tool_registry
            from frappe_assistant_core.utils.plugin_manager import get_plugin_manager

            # Get plugin manager for plugin info
            plugin_manager = get_plugin_manager()
            tool_registry = get_tool_registry()
            discovered_plugins = plugin_manager.get_discovered_plugins()
            enabled_plugins = plugin_manager.get_enabled_plugins()
            available_tools = plugin_manager.get_all_tools()

            # Include external tools from hooks (registered via assistant_tools)
            external_tools = tool_registry._get_external_tools()
            available_tools.update(external_tools)

            # Count active tools
            active_tools = len(
                [
                    tool_name
                    for tool_name, tool_info in available_tools.items()
                    if tool_info.plugin_name in enabled_plugins
                ]
            )
            total_tools = len(available_tools)

            # Build simplified HTML
            html = f"""
            <div class="p-3 rounded mb-3" style="background: var(--control-bg); border: 1px solid var(--border-color);">
                <div class="row align-items-center">
                    <div class="col-md-8">
                        <h5 class="mb-2" style="color: var(--heading-color);">
                            <i class="fa fa-cogs"></i> Plugin System Status
                        </h5>
                        <div class="row">
                            <div class="col-md-4">
                                <strong>Active Tools:</strong>
                                <span class="badge" style="background: var(--green-500); color: white;">{active_tools}</span>
                                / {total_tools}
                            </div>
                            <div class="col-md-4">
                                <strong>Plugins:</strong>
                                <span class="badge" style="background: var(--primary); color: white;">{len(enabled_plugins)}</span>
                                / {len(discovered_plugins)}
                            </div>
                            <div class="col-md-4">
                                <strong>Status:</strong>
                                <span style="color: var(--green-600);">
                                    <i class="fa fa-check-circle"></i> Operational
                                </span>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-4 text-right">
                        <a href="/app/fac-admin" class="btn btn-primary btn-sm">
                            <i class="fa fa-external-link-alt"></i> Open FAC Admin
                        </a>
                    </div>
                </div>
            </div>

            <div class="p-3 rounded" style="background: var(--card-bg); border: 1px solid var(--border-color);">
                <h6 style="color: var(--heading-color);"><i class="fa fa-puzzle-piece"></i> Plugins</h6>
                <div class="row mt-3">
            """

            # Show plugin summary cards
            for plugin in discovered_plugins:
                plugin_name = plugin.get("name", "Unknown")
                is_enabled = plugin_name in enabled_plugins
                plugin_tools = plugin.get("tools", [])
                tools_count = len(plugin_tools)

                status_color = "var(--green-500)" if is_enabled else "var(--gray-400)"
                status_text = "Active" if is_enabled else "Inactive"
                status_badge_bg = "var(--green-100)" if is_enabled else "var(--gray-100)"
                status_badge_color = "var(--green-700)" if is_enabled else "var(--gray-600)"

                html += f"""
                    <div class="col-md-6 mb-2">
                        <div class="p-2 rounded" style="background: var(--control-bg); border-left: 3px solid {status_color};">
                            <div class="d-flex justify-content-between align-items-center">
                                <div>
                                    <strong style="color: var(--heading-color);">{plugin.get("display_name", plugin_name.replace("_", " ").title())}</strong>
                                    <br>
                                    <small style="color: var(--text-muted);">{tools_count} tools</small>
                                </div>
                                <span class="badge" style="background: {status_badge_bg}; color: {status_badge_color};">
                                    {status_text}
                                </span>
                            </div>
                        </div>
                    </div>
                """

            html += """
                </div>
                <div class="mt-3 pt-2" style="border-top: 1px solid var(--border-color);">
                    <small style="color: var(--text-muted);">
                        <i class="fa fa-info-circle"></i>
                        For individual tool management, role-based access control, and category filtering,
                        use the <a href="/app/fac-admin">FAC Admin</a> page.
                    </small>
                </div>
            </div>
            """

            return {"success": True, "html": html}

        except Exception as e:
            return {
                "success": False,
                "html": f"<div class='p-3 rounded' style='background: var(--alert-bg-danger); color: var(--alert-text-danger);'>Error loading plugin status: {str(e)}</div>",
            }

    @frappe.whitelist()
    def toggle_plugin(self, plugin_name, action):
        """Enable or disable a plugin"""
        try:
            from frappe_assistant_core.utils.plugin_manager import PluginError, get_plugin_manager

            plugin_manager = get_plugin_manager()

            if action == "enable":
                result = plugin_manager.enable_plugin(plugin_name)
                message = _("Plugin '{0}' enabled successfully").format(plugin_name)
            elif action == "disable":
                result = plugin_manager.disable_plugin(plugin_name)
                message = _("Plugin '{0}' disabled successfully").format(plugin_name)
            else:
                frappe.throw(_("Invalid action: {0}").format(action))

            if result:
                frappe.msgprint(message)
                return {"success": True, "message": message}
            else:
                error_msg = _("Failed to {0} plugin '{1}'").format(action, plugin_name)
                frappe.throw(error_msg)

        except PluginError as e:
            frappe.log_error(title=frappe._("Plugin Toggle Error"), message=str(e))
            frappe.throw(frappe._(str(e)))
        except Exception as e:
            frappe.log_error(title=frappe._("Plugin Toggle Error"), message=str(e))
            frappe.throw(frappe._("Failed to {0} plugin '{1}': {2}").format(action, plugin_name, str(e)))


# SSE Bridge API endpoints removed - SSE transport is deprecated
# Use StreamableHTTP (OAuth-based) transport instead


@frappe.whitelist()
def toggle_plugin_api(plugin_name, action):
    """
    Standalone API to enable or disable a plugin.
    This is called from the HTML buttons in the plugin management UI.
    """
    try:
        from frappe_assistant_core.utils.plugin_manager import PluginError, get_plugin_manager

        plugin_manager = get_plugin_manager()

        if action == "enable":
            result = plugin_manager.enable_plugin(plugin_name)
            message = _("Plugin '{0}' enabled successfully").format(plugin_name)
        elif action == "disable":
            result = plugin_manager.disable_plugin(plugin_name)
            message = _("Plugin '{0}' disabled successfully").format(plugin_name)
        else:
            frappe.throw(_("Invalid action: {0}").format(action))

        if result:
            return {"success": True, "message": message}
        else:
            error_msg = _("Failed to {0} plugin '{1}'").format(action, plugin_name)
            frappe.throw(error_msg)

    except PluginError as e:
        frappe.log_error(title=frappe._("Plugin Toggle Error"), message=str(e))
        frappe.throw(frappe._(str(e)))
    except Exception as e:
        frappe.log_error(title=frappe._("Plugin Toggle Error"), message=str(e))
        frappe.throw(frappe._("Failed to {0} plugin '{1}': {2}").format(action, plugin_name, str(e)))


def get_context(context):
    context.title = _("assistant Server Settings")
    context.docs = _("Manage the settings for the assistant Server.")
    context.settings = frappe.get_doc("Assistant Core Settings")
