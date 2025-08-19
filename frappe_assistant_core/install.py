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
import json

from frappe_assistant_core.utils.logger import api_logger

def after_install():
    """Run after app installation"""
    
    api_logger.info("Installing Frappe assistant Server...")
    
    # First, make sure all DocTypes are synced
    frappe.db.commit()
    
    # Create default assistant Server Settings
    create_default_settings()
    
    # Create necessary roles first
    create_default_roles()
    
    # Create custom fields if needed
    create_custom_fields()
    
    # Setup permissions
    setup_permissions()
    
    # Register default plugins (tools are now managed through plugins)
    register_default_plugins()
    
    api_logger.info("Frappe assistant Server installed successfully!")
    api_logger.info("Please configure assistant Server Settings to enable the server.")

def create_default_settings():
    """Create default Assistant Core Settings"""
    try:
        # Ensure the DocType is properly loaded
        frappe.reload_doc("frappe_assistant_core", "doctype", "assistant_core_settings")
        
        if not frappe.db.exists("Assistant Core Settings", "Assistant Core Settings"):
            doc = frappe.get_doc({
                "doctype": "Assistant Core Settings",
                "server_enabled": 0,
                "enforce_artifact_streaming": 1,
                "response_limit_prevention": 1,
                "streaming_line_threshold": 5,
                "streaming_char_threshold": 1000,
                "enabled_plugins_list": json.dumps(["core"])  # Enable core plugin by default
            })
            doc.insert(ignore_permissions=True)
            api_logger.info("Created default Assistant Core Settings with core plugin enabled")
        else:
            # Update existing settings to ensure core plugin is enabled
            settings = frappe.get_single("Assistant Core Settings")
            enabled_plugins = json.loads(settings.enabled_plugins_list or "[]")
            if "core" not in enabled_plugins:
                enabled_plugins.append("core")
                settings.enabled_plugins_list = json.dumps(enabled_plugins)
                settings.save(ignore_permissions=True)
                api_logger.info("Updated Assistant Core Settings to enable core plugin")
            else:
                api_logger.info("Assistant Core Settings already exists with core plugin enabled")
    except Exception as e:
        api_logger.warning(f"Could not create Assistant Core Settings: {e}")

def register_default_plugins():
    """Register default plugins in the plugin repository"""
    try:
        # Ensure the DocType is properly loaded
        frappe.reload_doc("Assistant Core", "DocType", "Assistant Plugin Repository")
        
        # Check if Assistant Plugin Repository table exists
        if not frappe.db.table_exists("tabAssistant Plugin Repository"):
            api_logger.warning("Assistant Plugin Repository table not found, skipping plugin registration")
            return
        
        # Use the plugin repository refresh function to populate with discovered plugins
        from frappe_assistant_core.assistant_core.doctype.assistant_plugin_repository.assistant_plugin_repository import refresh_plugin_repository
        refresh_plugin_repository()
        
        api_logger.info("Successfully registered default plugins")
        
    except Exception as e:
        api_logger.warning(f"Could not register default plugins: {e}")
        # Try fallback registration
        try:
            api_logger.info("Attempting fallback plugin registration...")
            register_basic_plugins()
        except Exception as fallback_error:
            api_logger.error(f"Fallback plugin registration also failed: {fallback_error}")

def register_basic_plugins():
    """Fallback basic plugin registration"""
    try:
        from frappe_assistant_core.utils.plugin_manager import get_plugin_manager
        
        plugin_manager = get_plugin_manager()
        discovered_plugins = plugin_manager.get_discovered_plugins()
        
        plugins_created = 0
        for plugin_info in discovered_plugins:
            plugin_name = plugin_info.get('name')
            if not plugin_name:
                continue
                
            # Check if plugin already exists
            if not frappe.db.exists("Assistant Plugin Repository", plugin_name):
                doc = frappe.get_doc({
                    "doctype": "Assistant Plugin Repository",
                    "plugin_name": plugin_name,
                    "display_name": plugin_info.get('display_name', plugin_name),
                    "description": plugin_info.get('description', ''),
                    "version": plugin_info.get('version', ''),
                    "module_path": plugin_info.get('module_path', ''),
                    "enabled": plugin_name == 'core',  # Enable core plugin by default
                    "can_enable": plugin_info.get('can_enable', False),
                    "validation_error": plugin_info.get('validation_error', ''),
                    "dependencies": json.dumps(plugin_info.get('dependencies', [])),
                    "supported_tools": json.dumps(plugin_info.get('tools', [])),
                    "plugin_info": json.dumps(plugin_info)
                })
                doc.insert(ignore_permissions=True)
                plugins_created += 1
        
        api_logger.info(f"Registered {plugins_created} plugins via fallback method")
        
    except Exception as e:
        api_logger.error(f"Fallback plugin registration failed: {e}")

def create_default_roles():
    """Create default roles for assistant Server"""
    try:
        roles_to_create = [
            {
                "role_name": "Assistant User",
                "description": "Can use assistant tools and view connection logs"
            },
            {
                "role_name": "Assistant Admin", 
                "description": "Full access to assistant Server configuration and management"
            }
        ]
        
        for role_config in roles_to_create:
            if not frappe.db.exists("Role", role_config["role_name"]):
                # Create role
                role_doc = frappe.get_doc({
                    "doctype": "Role",
                    "role_name": role_config["role_name"],
                    "description": role_config["description"]
                })
                role_doc.insert(ignore_permissions=True)
        
        api_logger.info("Created default assistant roles")
        
    except Exception as e:
        api_logger.warning(f"Could not create default roles: {e}")

def create_custom_fields():
    """Create any necessary custom fields"""
    try:
        # Add assistant-related fields to User doctype if needed
        custom_fields = [
            {
                "doctype": "Custom Field",
                "dt": "User",
                "fieldname": "assistant_enabled",
                "label": "Enable Assistant Access",
                "fieldtype": "Check",
                "insert_after": "enabled",
                "description": "Allow this user to access assistant tools"
            }
        ]
        
        for field_config in custom_fields:
            if not frappe.db.exists("Custom Field", {"dt": field_config["dt"], "fieldname": field_config["fieldname"]}):
                frappe.get_doc(field_config).insert(ignore_permissions=True)
        
        api_logger.info("Created custom fields")
        
    except Exception as e:
        api_logger.warning(f"Could not create custom fields: {e}")

def setup_permissions():
    """Setup default permissions"""
    try:
        # Give System Manager role full access to assistant
        system_manager_perms = [
            "Assistant Core Settings",
 
            "Assistant Connection Log",
            "Assistant Audit Log"
        ]
        
        for doctype in system_manager_perms:
            if frappe.db.table_exists(f"tab{doctype}"):
                existing_perm = frappe.db.sql("""
                    SELECT name FROM `tabCustom DocPerm` 
                    WHERE parent = %s AND role = 'System Manager'
                    LIMIT 1
                """, (doctype,))
                
                if not existing_perm:
                    frappe.get_doc({
                        "doctype": "Custom DocPerm",
                        "parent": doctype,
                        "parenttype": "DocType",
                        "parentfield": "permissions",
                        "role": "System Manager",
                        "read": 1,
                        "write": 1,
                        "create": 1,
                        "delete": 1,
                        "submit": 0,
                        "cancel": 0,
                        "amend": 0
                    }).insert(ignore_permissions=True)
        
        api_logger.info("Setup default permissions")
        
    except Exception as e:
        api_logger.warning(f"Could not setup permissions: {e}")