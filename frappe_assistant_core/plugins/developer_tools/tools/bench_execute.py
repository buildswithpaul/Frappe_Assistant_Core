# Copyright (C) 2025 Promantia
# Developer Tools Plugin — bench_execute tool

import ast
import json
import os
import re
import shutil
import sys
from typing import Any, Dict

import frappe
import frappe.installer
from frappe import _

from frappe_assistant_core.core.base_tool import BaseTool
from frappe_assistant_core.plugins.developer_tools.tools import (
    PROTECTED_APPS,
    assert_system_manager,
)

_APP_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")

ALLOWED_FIXTURE_DOCTYPES = {
    "Custom Field",
    "Client Script",
    "Server Script",
    "Property Setter",
    "Role",
    "Workflow",
    "Print Format",
    "Notification",
}


def _convert_filters_to_list(filters: dict) -> list:
    result = []
    for field, value in filters.items():
        if isinstance(value, list) and len(value) == 2 and isinstance(value[0], str):
            result.append([field, value[0], value[1]])
        else:
            result.append([field, "=", value])
    return result


class BenchExecute(BaseTool):
    """
    Executes bench operations: list apps, create/install/uninstall/remove apps,
    and export fixtures. Always call bench_help first to know available actions and parameters.
    """

    def __init__(self):
        super().__init__()
        self.name = "bench_execute"
        self.description = (
            "Executes bench operations. Always call bench_help first to know available actions "
            "and parameters. Do NOT ask user for bench paths or site names."
        )
        self.category = "Developer Tools"
        self.source_app = "frappe_assistant_core"

        self.inputSchema = {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "Operation to perform.",
                    "enum": ["list_apps", "list_sites", "create_app", "install_app", "uninstall_app", "remove_app", "export_fixtures"],
                },
                "app_name": {
                    "type": "string",
                    "description": "Snake-case app name (required for all actions except list_apps).",
                },
                "doctype": {
                    "type": "string",
                    "description": "DocType to export as a fixture (only for export_fixtures).",
                },
                "filters": {
                    "type": "object",
                    "description": "Filters to specify which records to export (only for export_fixtures).",
                },
            },
            "required": ["action"],
        }

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        assert_system_manager()

        action = arguments.get("action")

        if action == "list_apps":
            bench_path = frappe.utils.get_bench_path()
            apps_path = os.path.join(bench_path, "apps")

            all_entries = os.listdir(apps_path)
            bench_apps = [
                entry for entry in all_entries
                if not entry.startswith(".")
                and entry not in PROTECTED_APPS
                and os.path.isdir(os.path.join(apps_path, entry))
            ]

            all_installed = frappe.get_installed_apps()
            site_apps = [
                app for app in all_installed
                if app not in PROTECTED_APPS
            ]

            ghosts = [
                app for app in all_installed
                if app not in PROTECTED_APPS
                and not os.path.isdir(os.path.join(apps_path, app))
            ]
            if ghosts:
                clean_list = [app for app in all_installed if app not in ghosts]
                frappe.db.set_global("installed_apps", frappe.as_json(clean_list))
                frappe.db.commit()
                site_apps = [app for app in site_apps if app not in ghosts]

            return {
                "success": True,
                "bench_apps": bench_apps,
                "bench_apps_count": len(bench_apps),
                "site_apps": site_apps,
                "site_apps_count": len(site_apps),
                "message": "bench_apps are all apps on disk. site_apps are apps installed on current site.",
            }

        elif action == "list_sites":
            bench_path = frappe.utils.get_bench_path()
            sites_path = os.path.join(bench_path, "sites")
            available_sites = []
            for item in os.listdir(sites_path):
                site_config = os.path.join(sites_path, item, "site_config.json")
                if os.path.isfile(site_config):
                    available_sites.append(item)
            return {
                "success": True,
                "sites": available_sites,
                "count": len(available_sites),
                "message": "These are the available sites on this bench.",
            }

        elif action == "create_app":
            app_name = arguments.get("app_name")
            if not app_name:
                frappe.throw("app_name is required for create_app.", frappe.ValidationError)

            if not _APP_NAME_RE.match(app_name):
                frappe.throw(
                    _(
                        "Invalid app_name '{0}'. Must match ^[a-z][a-z0-9_]*$ "
                        "(lowercase letters, digits, underscores; must start with a letter)."
                    ).format(app_name),
                    frappe.ValidationError,
                )

            if app_name in PROTECTED_APPS:
                frappe.throw(
                    _("Cannot create or overwrite protected app '{0}'.").format(app_name),
                    frappe.PermissionError,
                )

            bench_path = frappe.utils.get_bench_path()
            apps_path = os.path.join(bench_path, "apps")
            app_path = os.path.join(apps_path, app_name)

            if os.path.isdir(app_path):
                return {
                    "success": True,
                    "already_existed": True,
                    "installed": False,
                    "apps_txt_updated": False,
                    "app_name": app_name,
                    "message": f"App '{app_name}' already exists at {app_path}.",
                }

            app_title = arguments.get("app_title") or app_name.replace("_", " ").title()
            app_description = arguments.get("app_description") or ""

            hooks = frappe._dict(
                app_name=app_name,
                app_title=app_title,
                app_description=app_description,
                app_publisher="Promantia",
                app_email="dev@promantia.com",
                app_license="mit",
                create_github_workflow=False,
            )

            from frappe.utils.boilerplate import _create_app_boilerplate
            _create_app_boilerplate(apps_path, hooks, no_git=True)

            outer_init = os.path.join(apps_path, app_name, "__init__.py")
            if not os.path.exists(outer_init):
                open(outer_init, "w").close()

            pyproject = os.path.join(apps_path, app_name, "pyproject.toml")
            if not os.path.exists(pyproject):
                with open(pyproject, "w") as f:
                    f.write(f"""[project]
name = "{app_name}"
version = "0.0.1"

[build-system]
requires = ["flit_core >=3.2,<4"]
build-backend = "flit_core.buildapi"
""")

            from pip._internal.cli.main import main as pip_main
            pip_main(["install", "--quiet", "-e", os.path.join(apps_path, app_name)])

            if app_path not in sys.path:
                sys.path.insert(0, app_path)

            apps_txt_path = os.path.join(bench_path, "sites", "apps.txt")
            apps_txt_updated = False
            if os.path.exists(apps_txt_path):
                with open(apps_txt_path) as f:
                    existing = [line.strip() for line in f if line.strip()]
            else:
                existing = []

            if app_name not in existing:
                existing.append(app_name)
                with open(apps_txt_path, "w") as f:
                    f.write("\n".join(existing) + "\n")
                apps_txt_updated = True

            return {
                "success": True,
                "already_existed": False,
                "installed": False,
                "apps_txt_updated": apps_txt_updated,
                "app_name": app_name,
                "app_title": app_title,
                "message": f"App '{app_name}' created successfully. Use install_app to install it on the site.",
            }

        elif action == "install_app":
            app_name = arguments.get("app_name")
            if not app_name:
                frappe.throw(_("app_name is required for install_app."), frappe.ValidationError)

            frappe.installer.install_app(app_name)

            return {
                "success": True,
                "app_name": app_name,
                "message": f"App '{app_name}' installed on current site successfully.",
            }

        elif action == "uninstall_app":
            app_name = arguments.get("app_name")
            if not app_name:
                frappe.throw(_("app_name is required for uninstall_app."), frappe.ValidationError)

            installed = frappe.get_installed_apps()
            if app_name not in installed:
                return {
                    "success": False,
                    "app_name": app_name,
                    "message": f"App '{app_name}' is not installed on the current site.",
                }

            frappe.installer.remove_app(app_name, yes=True, no_backup=True)

            installed = frappe.get_installed_apps()
            if app_name in installed:
                new_list = [app for app in installed if app != app_name]
                frappe.db.set_global("installed_apps", frappe.as_json(new_list))
                frappe.db.commit()

            return {
                "success": True,
                "app_name": app_name,
                "message": f"App '{app_name}' uninstalled from current site successfully.",
            }

        elif action == "remove_app":
            app_name = arguments.get("app_name")
            if not app_name:
                frappe.throw(_("app_name is required for remove_app."), frappe.ValidationError)

            if app_name in PROTECTED_APPS:
                frappe.throw(
                    _("Cannot remove protected app '{0}'.").format(app_name),
                    frappe.PermissionError,
                )

            bench_path = frappe.utils.get_bench_path()
            app_path = os.path.join(bench_path, "apps", app_name)

            if not os.path.isdir(app_path):
                frappe.throw(
                    f"App '{app_name}' directory does not exist at {app_path}.",
                    frappe.ValidationError,
                )

            # Uninstall from site first if installed
            installed_apps = frappe.get_installed_apps()
            if app_name in installed_apps:
                frappe.installer.remove_app(app_name, yes=True, no_backup=True)
            else:
                # Still clean from DB just in case
                new_list = []
                for app in installed_apps:
                    if app != app_name:
                        new_list.append(app)
                frappe.db.set_global("installed_apps", frappe.as_json(new_list))
                frappe.db.commit()

            shutil.rmtree(app_path)

            # Remove from DB installed apps
            installed = frappe.get_installed_apps()
            if app_name in installed:
                new_list = [app for app in installed if app != app_name]
                frappe.db.set_global("installed_apps", frappe.as_json(new_list))
                frappe.db.commit()

            # Pip uninstall the package
            from pip._internal.cli.main import main as pip_main
            try:
                pip_main(["uninstall", "-y", app_name])
            except Exception:
                pass  # ignore if not pip installed

            apps_txt_path = os.path.join(bench_path, "sites", "apps.txt")
            apps_txt_updated = False
            if os.path.exists(apps_txt_path):
                with open(apps_txt_path) as f:
                    existing = [line.strip() for line in f if line.strip()]
                if app_name in existing:
                    existing.remove(app_name)
                    with open(apps_txt_path, "w") as f:
                        f.write("\n".join(existing) + "\n")
                    apps_txt_updated = True

            return {
                "success": True,
                "app_name": app_name,
                "apps_txt_updated": apps_txt_updated,
                "message": f"App '{app_name}' directory removed from bench successfully.",
            }

        elif action == "export_fixtures":
            if not arguments.get("app_name"):
                frappe.throw("app_name is required for export_fixtures.", frappe.ValidationError)
            if not arguments.get("doctype"):
                frappe.throw("MISSING REQUIRED PARAMETER: doctype. Cannot proceed without doctype. User must specify the DocType to export. Example: 'Custom Field', 'Property Setter', 'Client Script'", frappe.ValidationError)
            if not arguments.get("filters"):
                frappe.throw("MISSING REQUIRED PARAMETER: filters. Cannot proceed without filters. User must specify exact filters. Example: {\"dt\": \"Sales Invoice\"} or {\"module\": \"HR\"}", frappe.ValidationError)

            app_name = arguments.get("app_name")
            doctype = arguments.get("doctype")
            filters = arguments.get("filters") or {}

            if app_name in PROTECTED_APPS:
                frappe.throw(
                    _("Cannot export fixtures to protected app '{0}'.").format(app_name),
                    frappe.PermissionError,
                )

            bench_path = frappe.utils.get_bench_path()
            apps_path = os.path.join(bench_path, "apps")
            app_path = os.path.join(apps_path, app_name)

            if not os.path.isdir(app_path):
                frappe.throw(
                    f"App '{app_name}' does not exist on this bench. Use create_app to create it first.",
                    frappe.ValidationError,
                )

            if doctype not in ALLOWED_FIXTURE_DOCTYPES:
                frappe.throw(
                    _("DocType '{0}' is not allowed as a fixture. Allowed: {1}").format(
                        doctype, ", ".join(sorted(ALLOWED_FIXTURE_DOCTYPES))
                    ),
                    frappe.ValidationError,
                )

            records = frappe.get_all(doctype, filters=filters, fields=["*"])

            if not records:
                return {
                    "success": False,
                    "message": f"No {doctype} records found with given filters.",
                }

            full_records = []
            for record in records:
                doc = frappe.get_doc(doctype, record["name"])
                full_records.append(doc.as_dict())

            doctype_snake = frappe.scrub(doctype)
            fixture_dir = os.path.join(app_path, app_name, "fixtures")
            fixture_file = os.path.join(fixture_dir, f"{doctype_snake}.json")
            os.makedirs(fixture_dir, exist_ok=True)

            if os.path.exists(fixture_file):
                with open(fixture_file, "r") as f:
                    existing_data = json.load(f)
                existing_names = {r["name"] for r in existing_data}
                new_records = [r for r in full_records if r["name"] not in existing_names]
                existing_data.extend(new_records)
                final_records = existing_data
            else:
                final_records = full_records

            with open(fixture_file, "w") as f:
                json.dump(final_records, f, indent=2, default=str)

            hooks_file = os.path.join(app_path, app_name, "hooks.py")
            hooks_updated = False

            if os.path.exists(hooks_file):
                with open(hooks_file, "r") as f:
                    content = f.read()

                hooks_filters = _convert_filters_to_list(filters)
                new_entry = {"dt": doctype, "filters": hooks_filters}
                tree = ast.parse(content)
                fixtures_found = False

                for node in ast.walk(tree):
                    if isinstance(node, ast.Assign):
                        for target in node.targets:
                            if isinstance(target, ast.Name) and target.id == "fixtures":
                                fixtures_found = True
                                try:
                                    existing_entries = ast.literal_eval(node.value)
                                    existing_entry_index = None
                                    for i, e in enumerate(existing_entries):
                                        if isinstance(e, dict) and (e.get("dt") == doctype or e.get("doctype") == doctype):
                                            existing_entry_index = i
                                            break

                                    if existing_entry_index is None:
                                        existing_entries.append(new_entry)
                                        hooks_updated = True
                                    elif existing_entries[existing_entry_index] != new_entry:
                                        existing_entries[existing_entry_index] = new_entry
                                        hooks_updated = True

                                    if hooks_updated:
                                        new_fixtures_str = f"fixtures = {json.dumps(existing_entries, indent=4)}"
                                        lines = content.split("\n")
                                        start_line = node.lineno - 1
                                        end_line = node.end_lineno
                                        new_lines = (
                                            lines[:start_line]
                                            + new_fixtures_str.split("\n")
                                            + lines[end_line:]
                                        )
                                        content = "\n".join(new_lines)
                                except Exception:
                                    pass

                if not fixtures_found:
                    new_fixtures_str = f"\nfixtures = {json.dumps([new_entry], indent=4)}\n"
                    content += new_fixtures_str
                    hooks_updated = True

                with open(hooks_file, "w") as f:
                    f.write(content)

            return {
                "success": True,
                "app_name": app_name,
                "doctype": doctype,
                "records_exported": len(full_records),
                "fixture_file": os.path.join(app_name, app_name, "fixtures", f"{doctype_snake}.json"),
                "hooks_updated": hooks_updated,
                "message": f"{len(full_records)} {doctype} records exported to {app_name}",
            }

        else:
            frappe.throw(
                f"Unknown action '{action}'. Call bench_help to see available operations.",
                frappe.ValidationError,
            )


bench_execute = BenchExecute
