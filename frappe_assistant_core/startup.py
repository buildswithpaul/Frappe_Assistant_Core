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
Clean startup initialization using the new plugin manager.
Removes workarounds and provides proper initialization flow.
"""

import frappe

from frappe_assistant_core.utils.logger import api_logger


def startup():
    """App startup initialization"""
    try:
        # Persist encryption_key before any Password-field write (tenant_secret).
        # A missing/racy key corrupts FAC Chat Settings.tenant_secret on first
        # registration and surfaces as "Encryption key is invalid" on connect.
        from frappe_assistant_core.chat.tenant_credentials import ensure_encryption_key

        ensure_encryption_key()

        # Initialize plugin manager - this automatically loads enabled plugins from settings
        initialize_plugin_system()

        # Initialize assistant server if enabled
        settings = frappe.get_single("Assistant Core Settings")
        if settings and settings.server_enabled:
            from frappe_assistant_core.assistant_core.server import start_server

            start_server()

    except Exception as e:
        api_logger.debug(f"Startup error (non-critical): {e}")


def initialize_plugin_system():
    """Initialize the plugin system with clean architecture"""
    try:
        from frappe_assistant_core.utils.plugin_manager import get_plugin_manager

        # Get plugin manager - this automatically initializes and loads enabled plugins
        plugin_manager = get_plugin_manager()

        # Get stats for logging
        enabled_plugins = plugin_manager.get_enabled_plugins()
        available_tools = plugin_manager.get_all_tools()

        api_logger.info(
            f"Plugin system initialized: {len(enabled_plugins)} plugins enabled, "
            f"{len(available_tools)} tools available"
        )

    except Exception as e:
        api_logger.error(f"Failed to initialize plugin system: {e}")


# Legacy compatibility - can be removed after verifying no external calls
def load_enabled_plugins_from_settings():
    """Legacy compatibility function - now handled by plugin manager initialization"""
    api_logger.debug("load_enabled_plugins_from_settings called - delegating to plugin manager")
    initialize_plugin_system()


def ensure_enhanced_registry_initialized():
    """Legacy compatibility function - now handled by plugin manager initialization"""
    api_logger.debug("ensure_enhanced_registry_initialized called - delegating to plugin manager")
    initialize_plugin_system()
