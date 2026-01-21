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
Resources handlers for MCP protocol
Handles resources/list and resources/read requests

Serves tool documentation from docs/tools/*.md files as MCP resources.
Resources are only available when the resources feature is enabled in settings.
"""

import os
from typing import Any, Dict, List, Optional

import frappe
from frappe import _

from frappe_assistant_core.utils.logger import api_logger


class ResourceManager:
    """
    Centralized manager for MCP resource operations.
    Handles tool documentation resources.
    """

    TOOL_DOCS_PATH = "docs/tools"
    URI_SCHEME = "fac"

    def __init__(self):
        self.logger = frappe.logger("resource_manager")

    def is_resources_enabled(self) -> bool:
        """
        Check if resources feature is enabled in settings.

        Returns:
            True if resources feature is enabled, False otherwise
        """
        try:
            # Read directly from DB to avoid cache issues
            return bool(
                frappe.db.get_single_value("Assistant Core Settings", "enable_resources_feature") or 0
            )
        except Exception:
            return False

    def get_all_resources(self) -> List[Dict[str, Any]]:
        """
        Get all available tool documentation resources.

        Returns empty list if resources feature is disabled.

        Returns:
            List of resource metadata dicts in MCP format
        """
        if not self.is_resources_enabled():
            return []

        return self._get_tool_resources()

    def read_resource(self, uri: str) -> Dict[str, Any]:
        """
        Read resource content by URI.

        Args:
            uri: Resource URI (e.g., "fac://tools/list_documents")

        Returns:
            Resource content with metadata in MCP format

        Raises:
            frappe.ValidationError: If URI is invalid or resource not found
        """
        # Parse URI
        parsed = self._parse_uri(uri)
        if not parsed:
            frappe.throw(_("Invalid resource URI: {0}").format(uri), frappe.ValidationError)

        category, path = parsed

        if category == "tools":
            return self._read_tool_resource(path)
        else:
            frappe.throw(_("Unknown resource category: {0}").format(category), frappe.ValidationError)

    def _parse_uri(self, uri: str) -> Optional[tuple]:
        """
        Parse fac:// URI into (category, path).

        Args:
            uri: Full URI string

        Returns:
            Tuple of (category, path) or None if invalid
        """
        if not uri.startswith(f"{self.URI_SCHEME}://"):
            return None

        path = uri[len(f"{self.URI_SCHEME}://") :]
        parts = path.split("/", 1)

        if len(parts) < 2:
            return None

        return (parts[0], parts[1])

    # =========================================================================
    # Tool Documentation Resources
    # =========================================================================

    def _get_tool_resources(self) -> List[Dict[str, Any]]:
        """
        Get list of tool documentation resources.

        Scans docs/tools/ directory for .md files.

        Returns:
            List of resource metadata dicts
        """
        resources = []

        try:
            app_path = frappe.get_app_path("frappe_assistant_core")
            docs_path = os.path.join(app_path, self.TOOL_DOCS_PATH)

            if not os.path.exists(docs_path):
                self.logger.debug(f"Tool docs directory not found: {docs_path}")
                return resources

            for filename in os.listdir(docs_path):
                if filename.endswith(".md"):
                    tool_name = filename[:-3]  # Remove .md extension
                    resources.append(
                        {
                            "uri": f"{self.URI_SCHEME}://tools/{tool_name}",
                            "name": f"Tool: {tool_name}",
                            "description": f"Usage documentation for the {tool_name} tool",
                            "mimeType": "text/markdown",
                        }
                    )

        except Exception as e:
            self.logger.warning(f"Error scanning tool docs: {e}")

        return resources

    def _read_tool_resource(self, tool_name: str) -> Dict[str, Any]:
        """
        Read tool documentation file.

        Args:
            tool_name: Name of the tool (without .md extension)

        Returns:
            Resource content dict with uri, mimeType, and text

        Raises:
            frappe.ValidationError: If file not found
        """
        app_path = frappe.get_app_path("frappe_assistant_core")
        file_path = os.path.join(app_path, self.TOOL_DOCS_PATH, f"{tool_name}.md")

        if not os.path.exists(file_path):
            frappe.throw(_("Tool documentation not found: {0}").format(tool_name), frappe.ValidationError)

        with open(file_path, encoding="utf-8") as f:
            content = f.read()

        return {
            "uri": f"{self.URI_SCHEME}://tools/{tool_name}",
            "mimeType": "text/markdown",
            "text": content,
        }


# =============================================================================
# Singleton Instance
# =============================================================================

_resource_manager = None


def get_resource_manager() -> ResourceManager:
    """Get singleton instance of ResourceManager."""
    global _resource_manager
    if _resource_manager is None:
        _resource_manager = ResourceManager()
    return _resource_manager


# =============================================================================
# MCP Protocol Handlers
# =============================================================================


def handle_resources_list(params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Handle resources/list request.

    Returns empty list if resources feature is disabled.

    Args:
        params: Optional parameters (unused)

    Returns:
        Dict with resources list in MCP format
    """
    try:
        api_logger.debug("Processing resources/list request")

        manager = get_resource_manager()
        resources = manager.get_all_resources()

        api_logger.info(f"Resources list request completed, returned {len(resources)} resources")

        return {"resources": resources}

    except Exception as e:
        api_logger.error(f"Error in handle_resources_list: {e}")
        raise


def handle_resources_read(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle resources/read request.

    Args:
        params: Parameters containing 'uri' key

    Returns:
        Dict with contents list in MCP format

    Raises:
        frappe.ValidationError: If uri parameter missing or invalid
    """
    try:
        uri = params.get("uri")

        if not uri:
            frappe.throw(_("Missing required parameter: uri"), frappe.ValidationError)

        api_logger.debug(f"Processing resources/read request for: {uri}")

        manager = get_resource_manager()
        content = manager.read_resource(uri)

        api_logger.info(f"Resources read request completed for: {uri}")

        return {"contents": [content]}

    except (frappe.ValidationError, frappe.PermissionError):
        raise
    except Exception as e:
        api_logger.error(f"Error in handle_resources_read: {e}")
        raise
