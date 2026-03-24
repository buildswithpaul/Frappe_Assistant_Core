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
Core plugin providing essential Frappe operations.
This plugin is always enabled and provides fundamental tools.
"""

from frappe_assistant_core.plugins.base_plugin import BasePlugin


class CorePlugin(BasePlugin):
    """
    Core plugin that provides essential Frappe document and system operations.
    This plugin contains tools that should always be available.
    """

    def get_info(self):
        return {
            "name": "core",
            "display_name": "Core Operations",
            "description": "Essential Frappe document operations, search, metadata, and workflow tools",
            "version": "1.0.0",
            "dependencies": [],
            "requires_restart": False,
            "always_enabled": True,  # Special flag for core plugin
        }

    def get_tools(self):
        """
        Return list of core tool module names.
        These correspond to files in the core/tools directory.
        """
        return [
            # Individual document tools
            "create_document",
            "get_document",
            "update_document",
            "list_documents",
            "delete_document",
            "submit_document",
            # Search tools
            "search_documents",
            "search_doctype",
            "search_link",
            # ChatGPT-compatible tools (wrappers for ChatGPT MCP requirements)
            "chatgpt_search",
            "chatgpt_fetch",
            # Metadata tools
            "get_doctype_info",
            # Report tools (individual classes)
            "generate_report",
            "report_list",
            "report_requirements",
            # Workflow tools
            "run_workflow",
        ]

    def validate_environment(self):
        """Core plugin always validates successfully"""
        return True, None

    def on_enable(self):
        """Core plugin enable handler"""
        self.logger.info("Core plugin enabled (always active)")

    def on_disable(self):
        """Core plugin cannot be disabled"""
        self.logger.warning("Core plugin cannot be disabled")

    def get_capabilities(self):
        """Core capabilities"""
        return {
            "document_operations": {
                "create": True,
                "read": True,
                "update": True,
                "delete": True,
                "list": True,
            },
            "search": {"global_search": True, "doctype_search": True, "link_search": True},
            "metadata": {
                "doctype_info": True,
                "list_doctypes": True,
                "field_info": True,
                "permissions": True,
                "workflow": True,
            },
            "reporting": {"execute_reports": True, "list_reports": True, "report_details": True},
            "workflow": {"trigger_actions": True, "list_workflows": True, "check_status": True},
        }
