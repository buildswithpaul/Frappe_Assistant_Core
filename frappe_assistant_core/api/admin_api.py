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
from frappe import _

@frappe.whitelist()
def get_server_settings():
    """Fetch assistant Server Settings with caching."""
    from frappe_assistant_core.utils.cache import get_cached_server_settings
    
    return get_cached_server_settings()

@frappe.whitelist()
def update_server_settings(**kwargs):
    """Update Assistant Core Settings."""
    settings = frappe.get_single("Assistant Core Settings")
    
    # Update only the fields that are provided
    updated = False
    for field in ["server_enabled", "enforce_artifact_streaming", "response_limit_prevention", 
                  "streaming_line_threshold", "streaming_char_threshold"]:
        if field in kwargs:
            setattr(settings, field, kwargs[field])
            updated = True
    
    if updated:
        settings.save()
    
    return {"message": _("Assistant Core Settings updated successfully.")}

@frappe.whitelist()
def get_tool_registry():
    """Fetch assistant Tool Registry with detailed information."""
    from frappe_assistant_core.utils.plugin_manager import get_plugin_manager
    
    try:
        plugin_manager = get_plugin_manager()
        tools = plugin_manager.get_all_tools()
        enabled_plugins = plugin_manager.get_enabled_plugins()
        
        formatted_tools = []
        for tool_name, tool_info in tools.items():
            formatted_tools.append({
                "name": tool_name.replace('_', ' ').title(),
                "category": tool_info.plugin_name.replace('_', ' ').title(),
                "description": tool_info.description,
                "enabled": tool_info.plugin_name in enabled_plugins
            })
        
        # Sort by category and then by name
        formatted_tools.sort(key=lambda x: (x['category'], x['name']))
        
        return {"tools": formatted_tools}
    except Exception as e:
        frappe.log_error(f"Failed to get tool registry: {str(e)}")
        return {"tools": []}

@frappe.whitelist()
def get_plugin_stats():
    """Get plugin statistics for admin dashboard."""
    from frappe_assistant_core.utils.plugin_manager import get_plugin_manager
    
    try:
        plugin_manager = get_plugin_manager()
        discovered = plugin_manager.get_discovered_plugins()
        enabled = plugin_manager.get_enabled_plugins()
        
        plugins = []
        for plugin in discovered:
            plugins.append({
                'name': plugin['display_name'],
                'enabled': plugin['name'] in enabled
            })
        
        return {
            'enabled_count': len(enabled),
            'total_count': len(discovered),
            'plugins': plugins
        }
    except Exception as e:
        frappe.log_error(f"Failed to get plugin stats: {str(e)}")
        return {
            'enabled_count': 0,
            'total_count': 0,
            'plugins': []
        }

@frappe.whitelist()
def get_tool_stats():
    """Get tool statistics for admin dashboard."""
    from frappe_assistant_core.utils.plugin_manager import get_plugin_manager
    
    try:
        plugin_manager = get_plugin_manager()
        tools = plugin_manager.get_all_tools()
        
        categories = {}
        for tool_name, tool_info in tools.items():
            category = tool_info.plugin_name
            categories[category] = categories.get(category, 0) + 1
        
        return {
            'total_tools': len(tools),
            'categories': categories
        }
    except Exception as e:
        frappe.log_error(f"Failed to get tool stats: {str(e)}")
        return {
            'total_tools': 0,
            'categories': {}
        }

