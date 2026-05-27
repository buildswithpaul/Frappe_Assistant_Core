# Copyright (C) 2025 Promantia
# Developer Tools Plugin — bench_help tool

from typing import Any, Dict

from frappe_assistant_core.core.base_tool import BaseTool


class BenchHelp(BaseTool):
    """
    Returns all available bench operations with their required parameters.
    Always call this before bench_execute so you know what actions and parameters are available.
    """

    def __init__(self):
        super().__init__()
        self.name = "bench_help"
        self.description = (
            "Call this FIRST before any bench operation. Returns all available bench operations "
            "with their required parameters. Always call bench_help before bench_execute so you "
            "know what actions and parameters are available.\n\n"
            "INTERACTION RULES:\n"
            "1. After showing available operations, always ask user which operation they want as a question with each operation as a separate clickable option.\n"
            "2. When user asks what operations are available, call this tool then present each action as a separate option in a question format.\n"
            "3. When user wants to remove, uninstall or install an app without specifying which app, first call bench_execute with list_apps, then present each app as a separate clickable option in a question."
        )
        self.category = "Developer Tools"
        self.source_app = "frappe_assistant_core"

        self.inputSchema = {
            "type": "object",
            "properties": {},
        }

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "success": True,
            "actions": [
                {
                    "action": "list_apps",
                    "description": "List all apps on bench and apps installed on site separately",
                    "params": [],
                },
                {
                    "action": "list_sites",
                    "description": "List all available sites on this bench",
                    "params": [],
                },
                {
                    "action": "create_app",
                    "description": "Create a new custom Frappe app on bench",
                    "params": ["app_name", "app_title (optional)", "app_description (optional)"],
                },
                {
                    "action": "install_app",
                    "description": "Install an existing bench app onto the current site",
                    "params": ["app_name"],
                },
                {
                    "action": "uninstall_app",
                    "description": "Uninstall app from current site only, keeps files on bench",
                    "params": ["app_name"],
                },
                {
                    "action": "remove_app",
                    "description": "Permanently remove app from bench — uninstalls from site, pip uninstalls package, removes directory",
                    "params": ["app_name"],
                },
                {
                    "action": "export_fixtures",
                    "description": (
                        "Export DocType customizations as fixtures to a custom app. REQUIRED params: app_name, doctype, filters. Tool will FAIL if any are missing.\n\n"
                        "ALLOWED DOCTYPES for export:\n"
                        "- Custom Field → filter by: dt (DocType name)\n"
                        "- Property Setter → filter by: doc_type, field_name\n"
                        "- Client Script → filter by: dt, module\n"
                        "- Server Script → filter by: name, module\n"
                        "- Role → filter by: name\n"
                        "- Workflow → filter by: document_type\n"
                        "- Print Format → filter by: doc_type, module\n"
                        "- Notification → filter by: document_type, module\n\n"
                        "Always provide very specific filters. Examples:\n"
                        "- Custom Field: {\"dt\": \"Sales Invoice\"}\n"
                        "- Property Setter: {\"doc_type\": \"Sales Invoice\", \"field_name\": \"max_discount\"}\n"
                        "- Server Script: {\"name\": [\"in\", [\"script1\", \"script2\"]]}\n"
                        "- Role: {\"name\": [\"in\", [\"Accounts Manager\", \"Stock Manager\"]]}\n\n"
                        "The more specific the filters, the fewer and more precise the records exported."
                    ),
                    "params": ["app_name", "doctype", "filters"],
                },
            ],
        }


bench_help = BenchHelp
