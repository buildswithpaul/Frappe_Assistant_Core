# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""FAC Tool Configuration DocType for individual tool enable/disable and access control."""

import frappe
from frappe import _
from frappe.model.document import Document


class FACToolConfiguration(Document):
    """
    Document class for FAC Tool Configuration.

    Fields:
        tool_name: Unique identifier for the tool
        plugin_name: Name of the plugin that provides this tool
        description: Tool description
        enabled: Whether the tool is enabled (default: 1)
        tool_category: Category of the tool (read_only, write, read_write, privileged)
        auto_detected_category: Automatically detected category
        category_override: Whether the category has been manually overridden
        role_access_mode: Access mode (Allow All, Restrict to Listed Roles)
        role_access: Child table of roles with access
        source_app: Source application providing the tool
        module_path: Python module path for the tool
    """

    def validate(self):
        """Validate tool configuration."""
        self._validate_category()
        self._validate_role_access()

    def _validate_category(self):
        """Ensure category is set and handle override logic."""
        if self.category_override and not self.tool_category:
            frappe.throw(_("Please select a Tool Category when override is enabled"))

        # If not overridden, use auto-detected category
        if not self.category_override and self.auto_detected_category:
            self.tool_category = self.auto_detected_category

    def _validate_role_access(self):
        """Validate role access configuration."""
        if self.role_access_mode == "Restrict to Listed Roles" and not self.role_access:
            frappe.throw(_("Please add at least one role when using 'Restrict to Listed Roles' mode"))

    def on_update(self):
        """Clear caches when tool configuration changes."""
        self._clear_tool_caches()

    def on_trash(self):
        """Clear caches when tool configuration is deleted."""
        self._clear_tool_caches()

    def _clear_tool_caches(self):
        """Clear all tool-related caches."""
        cache = frappe.cache()
        cache.delete_keys(f"fac_tool_config_{self.tool_name}")
        cache.delete_keys("fac_tool_configurations")
        cache.delete_keys("fac_tool_registry_*")

    def user_has_access(self, user: str = None) -> bool:
        """
        Check if a user has access to this tool based on role configuration.

        Args:
            user: User email (defaults to current session user)

        Returns:
            True if user has access, False otherwise
        """
        user = user or frappe.session.user

        # Tool must be enabled
        if not self.enabled:
            return False

        # Allow All mode - everyone has access
        if self.role_access_mode == "Allow All":
            return True

        # System Manager always has access
        user_roles = set(frappe.get_roles(user))
        if "System Manager" in user_roles:
            return True

        # Check if any of user's roles are in the allowed list
        for role_access in self.role_access:
            if role_access.role in user_roles and role_access.allow_access:
                return True

        return False


@frappe.whitelist()
def get_tool_access_status(tool_name: str, user: str = None) -> dict:
    """
    Check if a user has access to a specific tool.

    Args:
        tool_name: Name of the tool
        user: User email (defaults to current session user)

    Returns:
        Dict with access status and reason
    """
    user = user or frappe.session.user

    try:
        config = frappe.get_doc("FAC Tool Configuration", tool_name)
        has_access = config.user_has_access(user)

        return {
            "tool_name": tool_name,
            "user": user,
            "has_access": has_access,
            "enabled": config.enabled,
            "role_access_mode": config.role_access_mode,
            "tool_category": config.tool_category,
        }
    except frappe.DoesNotExistError:
        # No config means tool is allowed by default
        return {
            "tool_name": tool_name,
            "user": user,
            "has_access": True,
            "enabled": True,
            "role_access_mode": "Allow All",
            "tool_category": None,
            "note": "No configuration exists - using defaults",
        }


@frappe.whitelist()
def toggle_tool(tool_name: str, enabled: bool) -> dict:
    """
    Enable or disable a tool.

    Args:
        tool_name: Name of the tool
        enabled: True to enable, False to disable

    Returns:
        Dict with success status
    """
    try:
        config = frappe.get_doc("FAC Tool Configuration", tool_name)
        config.enabled = 1 if enabled else 0
        config.save(ignore_permissions=True)

        return {
            "success": True,
            "tool_name": tool_name,
            "enabled": config.enabled,
            "message": _("Tool '{0}' {1}").format(tool_name, _("enabled") if enabled else _("disabled")),
        }
    except frappe.DoesNotExistError:
        return {
            "success": False,
            "message": _("Tool configuration not found: {0}").format(tool_name),
        }
    except Exception as e:
        frappe.log_error(title=_("Tool Toggle Error"), message=str(e))
        return {"success": False, "message": str(e)}


@frappe.whitelist()
def bulk_toggle_tools(tool_names: list, enabled: bool) -> dict:
    """
    Enable or disable multiple tools at once.

    Args:
        tool_names: List of tool names
        enabled: True to enable, False to disable

    Returns:
        Dict with success count and failures
    """
    if isinstance(tool_names, str):
        import json

        tool_names = json.loads(tool_names)

    success_count = 0
    failures = []

    for tool_name in tool_names:
        result = toggle_tool(tool_name, enabled)
        if result.get("success"):
            success_count += 1
        else:
            failures.append({"tool_name": tool_name, "error": result.get("message")})

    return {
        "success": len(failures) == 0,
        "total": len(tool_names),
        "success_count": success_count,
        "failures": failures,
        "message": _("{0} of {1} tools updated").format(success_count, len(tool_names)),
    }
