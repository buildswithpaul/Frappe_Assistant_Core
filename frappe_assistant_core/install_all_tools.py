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
Script to verify and list all available tools from the plugin system.
Tools are now auto-discovered through the plugin architecture, 
no manual registration needed.
"""

import frappe
from frappe_assistant_core.utils.logger import api_logger

def list_all_tools():
    """List all available tools from the plugin system"""
    
    try:
        # Use the plugin manager to discover all tools
        from frappe_assistant_core.utils.plugin_manager import get_plugin_manager
        from frappe_assistant_core.core.tool_registry import get_tool_registry
        
        # Get plugin manager and discover plugins
        plugin_manager = get_plugin_manager()
        discovered_plugins = plugin_manager.get_discovered_plugins()
        
        api_logger.info(f"Discovered {len(discovered_plugins)} plugins")
        
        # Load all discovered plugins to get their tools
        plugin_names = [p.get('name') for p in discovered_plugins if p.get('name')]
        plugin_manager.load_enabled_plugins(plugin_names)
        
        # Get tool registry with all tools loaded
        registry = get_tool_registry()
        available_tools = registry.get_available_tools()
        
        api_logger.info(f"Found {len(available_tools)} tools from plugins:")
        
        # List tools by plugin
        tools_by_plugin = {}
        for tool in available_tools:
            tool_name = tool.get('name')
            # Group tools by their prefix to estimate plugin
            if tool_name:
                prefix = tool_name.split('_')[0] if '_' in tool_name else 'misc'
                if prefix not in tools_by_plugin:
                    tools_by_plugin[prefix] = []
                tools_by_plugin[prefix].append(tool_name)
        
        for prefix, tools in sorted(tools_by_plugin.items()):
            api_logger.info(f"  {prefix}: {', '.join(sorted(tools))}")
        
        return available_tools
        
    except Exception as e:
        api_logger.error(f"Failed to list tools: {e}")
        import traceback
        traceback.print_exc()
        return []

def verify_tool_system():
    """Verify the tool system is working correctly"""
    try:
        tools = list_all_tools()
        if tools:
            api_logger.info("✓ Tool system is working correctly")
            api_logger.info(f"✓ {len(tools)} tools are available")
            return True
        else:
            api_logger.warning("⚠ No tools found - check plugin configuration")
            return False
    except Exception as e:
        api_logger.error(f"✗ Tool system verification failed: {e}")
        return False

# For backward compatibility
def register_all_tools():
    """Legacy function - tools are now auto-discovered, no registration needed"""
    api_logger.info("Tool registration is no longer needed - tools are auto-discovered through plugins")
    return verify_tool_system()

if __name__ == "__main__":
    verify_tool_system()