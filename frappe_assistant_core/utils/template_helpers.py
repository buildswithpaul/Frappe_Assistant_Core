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

def get_assistant_status():
    """Template helper to get assistant server status"""
    try:
        from frappe_assistant_core.assistant_core.server import get_server_status
        return get_server_status()
    except Exception:
        return {"running": False, "enabled": False}

def get_tool_count():
    """Template helper to get count of enabled tools"""
    try:
        from frappe_assistant_core.utils.plugin_manager import get_plugin_manager
        plugin_manager = get_plugin_manager()
        all_tools = plugin_manager.get_all_tools()
        return len(all_tools)
    except Exception:
        return 0

def format_execution_time(seconds):
    """Format execution time for display"""
    if not seconds:
        return "N/A"
    
    if seconds < 1:
        return f"{int(seconds * 1000)}ms"
    else:
        return f"{seconds:.2f}s"

def get_connection_status_color(status):
    """Get color for connection status"""
    colors = {
        "Connected": "green",
        "Disconnected": "gray", 
        "Error": "red",
        "Timeout": "orange"
    }
    return colors.get(status, "gray")