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
                    "description": (
                        "List ALL apps on bench and ALL apps installed on the site — "
                        "including frappe, erpnext, and other core apps. "
                        "No apps are hidden. Use this to get a complete picture before "
                        "any install, uninstall, or remove operation."
                    ),
                    "params": [],
                },
                {
                    "action": "list_sites",
                    "description": "List all available sites on this bench",
                    "params": [],
                },
                {
                    "action": "create_app",
                    "description": (
                        "Create a new custom Frappe app on bench. "
                        "FULL FLOW after create_app: "
                        "1. Call install_app to install the new app on the site. "
                        "2. Immediately verify the Python import works: "
                        "bench --site {site} execute \"import {app_name}; print('ok')\". "
                        "If import fails the scaffold is broken — run remove_app and recreate. "
                        "Never proceed with a broken app."
                    ),
                    "params": ["app_name", "app_title (optional)", "app_description (optional)"],
                },
                {
                    "action": "install_app",
                    "description": (
                        "Install an existing bench app onto a site. "
                        "SITE SELECTION RULE: Call list_sites first. "
                        "If list_sites returns more than one site, you MUST show the list to the user and ask: "
                        "'I found these sites: [list all sites]. Which site should I use?' "
                        "NEVER pick a site automatically when multiple sites exist. "
                        "NEVER proceed without the user choosing a site. "
                        "VERIFY AFTER INSTALL: After installing, verify the Python import works by running: "
                        "bench --site {site} execute \"import {app_name}; print('ok')\". "
                        "If the import fails, immediately alert the user and do not proceed further."
                    ),
                    "params": ["app_name"],
                },
                {
                    "action": "uninstall_app",
                    "description": (
                        "Uninstall app from a site only, keeps files on bench. "
                        "SITE SELECTION RULE: Call list_sites first. "
                        "If list_sites returns more than one site, you MUST show the list to the user and ask: "
                        "'I found these sites: [list all sites]. Which site should I use?' "
                        "NEVER pick a site automatically when multiple sites exist. "
                        "NEVER proceed without the user choosing a site."
                    ),
                    "params": ["app_name"],
                },
                {
                    "action": "remove_app",
                    "description": (
                        "Permanently remove app from bench — uninstalls from site, pip uninstalls package, removes directory. "
                        "SAFETY RULE — before removing any app: "
                        "1. Call list_apps to show what is installed. "
                        "2. Warn the user: 'This will permanently delete {app_name} and all its files'. "
                        "3. Ask: 'Are you sure? (Yes/No)'. "
                        "4. Only proceed if the user confirms Yes. "
                        "5. Never remove frappe, erpnext, hrms, payments, frappe_assistant_core, "
                        "or any app that other apps depend on."
                    ),
                    "params": ["app_name"],
                },
                {
                    "action": "migrate",
                    "description": (
                        "Run bench migrate on a site to register new reports, doctypes and other changes in the database. "
                        "Always run this after write_file creates report or doctype files. "
                        "LOCK CHECK: Before running migrate, check for a stale lock file. "
                        "Run 'ps aux' to confirm bench migrate is not already running. "
                        "If migrate IS running: alert the user and stop. "
                        "If migrate is NOT running but sites/{site}/locks/bench_migrate.lock exists: "
                        "delete the lock file automatically, then proceed. "
                        "After migrate, bench restart runs automatically (restart=true by default) to reload workers. "
                        "Pass build_assets=true and app_name to also rebuild JS/CSS assets with bench build. "
                        "VERIFY AFTER MIGRATE: After migrate completes, verify new doctypes are registered by running: "
                        "frappe.db.get_all('DocType', {'module': '{app_module}'}). "
                        "If expected doctypes are missing, alert the user. "
                        "SITE SELECTION RULE: Call list_sites first. "
                        "If list_sites returns more than one site, you MUST show the list to the user and ask: "
                        "'I found these sites: [list all sites]. Which site should I use?' "
                        "NEVER pick a site automatically when multiple sites exist. "
                        "NEVER proceed without the user choosing a site."
                    ),
                    "params": [
                        "restart (boolean, default true)",
                        "build_assets (boolean, default false)",
                        "app_name (required when build_assets=true)",
                    ],
                },
                {
                    "action": "migrate_status",
                    "description": (
                        "Check whether a background bench migrate is still running. "
                        "Call this immediately after migrate returns background=True. "
                        "If still_running=True, wait 15 seconds and call migrate_status again. "
                        "Keep polling until still_running=False, then report migration complete to the user. "
                        "Do NOT wait for the user to ask — poll automatically after each migrate."
                    ),
                    "params": [],
                },
                {
                    "action": "export_fixtures",
                    "description": (
                        "Export DocType customizations as fixtures to a custom app. REQUIRED params: app_name, doctype, filters. Tool will FAIL if any are missing. "
                        "SITE SELECTION RULE: Call list_sites first. "
                        "If list_sites returns more than one site, you MUST show the list to the user and ask: "
                        "'I found these sites: [list all sites]. Which site should I use?' "
                        "NEVER pick a site automatically when multiple sites exist. "
                        "NEVER proceed without the user choosing a site.\n\n"
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
                        '- Custom Field: {"dt": "Sales Invoice"}\n'
                        '- Property Setter: {"doc_type": "Sales Invoice", "field_name": "max_discount"}\n'
                        '- Server Script: {"name": ["in", ["script1", "script2"]]}\n'
                        '- Role: {"name": ["in", ["Accounts Manager", "Stock Manager"]]}\n\n'
                        "The more specific the filters, the fewer and more precise the records exported."
                    ),
                    "params": ["app_name", "doctype", "filters"],
                },
            ],
        }


bench_help = BenchHelp
